# file: src/infrastructure/services/audio/voice_recording.py
# requirements: sounddevice, numpy
# pip install sounddevice numpy

import queue
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd


class VoiceRecording:
    """
    Запись WAV с автозавершением после N секунд непрерывной ТИШИНЫ.
    Особенности:
      - Опциональная автокалибровка шумового фона (auto_calibrate).
      - Гистерезис порогов: voice_on_rms > voice_off_rms.
      - Файл send_audio.wav сохраняется рядом с модулем и перезаписывается.
      - Безопасное открытие/закрытие устройства (замок + ретраи) для macOS AUHAL.

    Рекомендуемые параметры для «моментального» старта по ключевому слову:
      auto_calibrate=False, require_voice_first=False, blocksize=1024–2048.
    """

    def __init__(
        self,
        samplerate: Optional[int] = None,   # None => взять дефолт девайса (часто 48000)
        channels: int = 1,
        blocksize: int = 2048,              # меньше блок → ниже латентность
        dtype: str = "int16",
        silence_duration: float = 2.0,
        # Стартовые пороги (могут быть обновлены при auto_calibrate=True)
        voice_on_rms: float = 350.0,
        voice_off_rms: float = 250.0,
        # Автокалибровка
        auto_calibrate: bool = False,
        calib_max_time: float = 1.0,        # максимум времени на калибровку
        margin_on: float = 120.0,           # дельта к шуму для "включить речь"
        margin_off: float = 60.0,           # дельта к шуму для "тишины"
        device_index: Optional[int] = None,
        filename: str = "send_audio.wav",
        require_voice_first: bool = False,  # писать сразу, не ждать первой речи
        debug_rms: bool = False,
    ):
        self.device_index = device_index

        # Определим samplerate устройства при необходимости
        if samplerate is None:
            if device_index is not None:
                dev = sd.query_devices(device_index)
            else:
                dev = sd.query_devices(kind="input")
            samplerate = int(dev["default_samplerate"])

        self.samplerate = int(samplerate)
        self.channels = int(channels)
        self.blocksize = int(blocksize)
        self.dtype = dtype

        self.silence_duration = float(silence_duration)
        self.voice_on_rms = float(voice_on_rms)
        self.voice_off_rms = float(voice_off_rms)
        self.auto_calibrate = bool(auto_calibrate)
        self.calib_max_time = float(calib_max_time)
        self.margin_on = float(margin_on)
        self.margin_off = float(margin_off)
        self.require_voice_first = bool(require_voice_first)
        self.debug_rms = bool(debug_rms)

        # Файл рядом с модулем
        self.base_dir = Path(__file__).resolve().parent
        self.outfile = self.base_dir / filename

        # Внутреннее состояние
        self._q: "queue.Queue[bytes]" = queue.Queue()
        self._running = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._stream: Optional[sd.RawInputStream] = None
        self._on_done: Optional[Callable[[Path], None]] = None

        # Защита операций на микрофоне (AUHAL)
        self._mic_lock = threading.Lock()

    # ---------------------- публичный API ----------------------

    def record_async(self, on_done: Callable[[Path], None]) -> None:
        """Старт записи; on_done(path) будет вызван после остановки по тишине."""
        if self._running.is_set():
            return

        # Перезапишем файл
        try:
            if self.outfile.exists():
                self.outfile.unlink()
        except Exception:
            pass

        self._on_done = on_done
        self._running.set()

        # Открытие устройства под замок с ретраями
        with self._mic_lock:
            self._open_stream_with_retry()
        # краткая пауза — дать AUHAL стабилизироваться
        time.sleep(0.02)

        self._worker = threading.Thread(target=self._loop, name="silence-recorder", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        """Принудительная остановка записи."""
        self._running.clear()
        with self._mic_lock:
            try:
                if self._stream:
                    self._stream.stop()
                    self._stream.close()
            finally:
                self._stream = None
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=2)
        # дать CoreAudio «отпустить» устройство
        time.sleep(0.05)

    # ---------------------- внутреннее ----------------------

    def _open_stream_with_retry(self, retries: int = 3, delay_s: float = 0.15):
        """Открыть RawInputStream с учётом капризов AUHAL: ретраи + задержка."""
        last_err = None
        # Проверим доступность каналов у выбранного устройства
        dev = sd.query_devices(self.device_index) if self.device_index is not None else sd.query_devices(kind="input")
        max_in = int(dev.get("max_input_channels", 0))
        if max_in < 1:
            raise RuntimeError("Нет доступных входных каналов у устройства.")
        if self.channels > max_in:
            self.channels = max_in  # ограничим

        for _ in range(retries):
            try:
                self._stream = sd.RawInputStream(
                    samplerate=self.samplerate,
                    blocksize=self.blocksize,
                    dtype=self.dtype,
                    channels=self.channels,
                    device=self.device_index,
                    callback=self._cb,
                )
                self._stream.start()
                return
            except Exception as e:
                last_err = e
                time.sleep(delay_s)
        raise last_err

    def _cb(self, indata, frames, time_info, status):
        # Полезно логировать статус при отладке:
        # if status:
        #     print(f"[SD] status: {status}")
        self._q.put(bytes(indata))

    @staticmethod
    def _rms_int16(buf: bytes) -> float:
        a = np.frombuffer(buf, dtype=np.int16)
        if a.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(a.astype(np.float32) ** 2)))

    def _calibrate_thresholds(self, deadline: float) -> None:
        """
        Короткая оценка шумового фона (до deadline). Если речь появится раньше — выходим.
        Обновляет self.voice_on_rms и self.voice_off_rms.
        """
        rms_values = []
        while time.monotonic() < deadline and self._running.is_set():
            try:
                data = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            rms = self._rms_int16(data)
            rms_values.append(rms)
            if rms >= self.voice_on_rms:
                break  # речь началась — хватит калибровки

        if not rms_values:
            return

        noise_rms = float(np.median(rms_values))
        on_new = max(noise_rms + self.margin_on, noise_rms * 1.5)
        off_new = max(noise_rms + self.margin_off, noise_rms * 1.2)

        # Гарантируем гистерезис
        if off_new >= on_new:
            off_new = max(noise_rms + self.margin_off, on_new * 0.7)

        self.voice_on_rms = on_new
        self.voice_off_rms = off_new

        if self.debug_rms:
            print(f"[CALIB] noise={noise_rms:.1f}, on={self.voice_on_rms:.1f}, off={self.voice_off_rms:.1f}")

    def _loop(self):
        """
        Состояния:
          - waiting_voice: ждём первый голос (если require_voice_first=True).
          - recording: считаем непрерывную тишину; при превышении silence_duration — остановка.
        """
        state = "waiting_voice" if self.require_voice_first else "recording"
        silence_started_at: float | None = None

        # Опциональная автокалибровка порогов перед записью
        if self.auto_calibrate:
            self._calibrate_thresholds(deadline=time.monotonic() + self.calib_max_time)

        with wave.open(str(self.outfile), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self.samplerate)

            while self._running.is_set():
                try:
                    data = self._q.get(timeout=0.5)
                except queue.Empty:
                    # Продолжаем отсчёт тишины, если он идёт
                    if state == "recording" and silence_started_at is not None:
                        if time.monotonic() - silence_started_at >= self.silence_duration:
                            break
                    continue

                # Пишем всё (и голос, и паузы), чтобы сохранить естественный хвост
                wf.writeframesraw(data)

                rms = self._rms_int16(data)
                if self.debug_rms:
                    print(f"[RMS] {rms:.1f} (on={self.voice_on_rms:.1f}, off={self.voice_off_rms:.1f})")

                if state == "waiting_voice":
                    if rms >= self.voice_on_rms:
                        state = "recording"
                        silence_started_at = None
                    # продолжаем писать, но тишину не считаем
                    continue

                # state == "recording"
                if rms >= self.voice_on_rms:
                    # есть голос — сброс таймера тишины
                    silence_started_at = None
                    continue

                # зона тишины / почти тишины
                if rms <= self.voice_off_rms:
                    if silence_started_at is None:
                        silence_started_at = time.monotonic()
                    elif time.monotonic() - silence_started_at >= self.silence_duration:
                        break
                else:
                    # между off и on — считаем как «не тишина»
                    silence_started_at = None

                # Корректно завершим WAV
                wf.writeframes(b"")

            # === освободить устройство ===
            with self._mic_lock:
                try:
                    if self._stream:
                        self._stream.stop()
                        self._stream.close()
                finally:
                    self._stream = None
                    self._running.clear()

            # === уведомить верхний уровень (файл готов) ===
            cb = self._on_done
            self._on_done = None
            path = self.outfile
            if cb and path.exists() and path.stat().st_size > 0:
                try:
                    cb(path)
                except Exception:
                    pass