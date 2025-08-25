# file: src/infrastructure/services/audio/voice_recording.py
# requirements: sounddevice, numpy
# pip install sounddevice numpy

import queue
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd


class VoiceRecording:
    """
    Запись в raw PCM16 (s16le) с автозавершением после N секунд тишины.

    Особенности:
      - Файл send_audio.pcm сохраняется рядом с модулем и перезаписывается.
      - Автокалибровка шумового фона (опционально).
      - Гистерезис порогов: voice_on_rms > voice_off_rms.
    """

    def __init__(
        self,
        samplerate: int = 24000,
        channels: int = 1,
        blocksize: int = 2048,
        dtype: str = "int16",
        silence_duration: float = 1.0,
        voice_on_rms: float = 350.0,
        voice_off_rms: float = 250.0,
        auto_calibrate: bool = False,
        calib_max_time: float = 1.0,
        margin_on: float = 120.0,
        margin_off: float = 60.0,
        device_index: Optional[int] = None,
        filename: str = "send_audio.pcm",
        require_voice_first: bool = False,
        debug_rms: bool = True,
    ):
        self.device_index = device_index
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

        self.base_dir = Path(__file__).resolve().parent
        self.outfile = self.base_dir / Path(filename).with_suffix(".pcm")

        self._q: "queue.Queue[bytes]" = queue.Queue()
        self._running = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._stream: Optional[sd.RawInputStream] = None
        self._on_done: Optional[Callable[[Path], None]] = None
        self._mic_lock = threading.Lock()

    # ---------------------- API ----------------------

    def record_async(self, on_done: Callable[[Path], None]) -> None:
        """Старт записи; on_done(path) вызовется после остановки по тишине."""
        if self._running.is_set():
            return

        if self.outfile.exists():
            try:
                self.outfile.unlink()
            except Exception:
                pass

        self._on_done = on_done
        self._running.set()

        with self._mic_lock:
            self._open_stream_with_retry()
        time.sleep(0.02)

        self._worker = threading.Thread(target=self._loop, name="pcm16-recorder", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        """Принудительная остановка."""
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
        time.sleep(0.05)

    # ---------------------- внутренняя логика ----------------------

    def _open_stream_with_retry(self, retries: int = 3, delay_s: float = 0.15):
        last_err = None
        dev = sd.query_devices(self.device_index) if self.device_index is not None else sd.query_devices(kind="input")
        max_in = int(dev.get("max_input_channels", 0))
        if max_in < 1:
            raise RuntimeError("Нет доступных входных каналов.")
        if self.channels > max_in:
            self.channels = max_in

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
        self._q.put(bytes(indata))

    @staticmethod
    def _rms_int16(buf: bytes) -> float:
        a = np.frombuffer(buf, dtype=np.int16)
        if a.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(a.astype(np.float32) ** 2)))

    def _calibrate_thresholds(self, deadline: float) -> None:
        rms_values = []
        while time.monotonic() < deadline and self._running.is_set():
            try:
                data = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            rms = self._rms_int16(data)
            rms_values.append(rms)
            if rms >= self.voice_on_rms:
                break

        if not rms_values:
            return

        noise_rms = float(np.median(rms_values))
        on_new = max(noise_rms + self.margin_on, noise_rms * 1.5)
        off_new = max(noise_rms + self.margin_off, noise_rms * 1.2)
        if off_new >= on_new:
            off_new = max(noise_rms + self.margin_off, on_new * 0.7)

        self.voice_on_rms, self.voice_off_rms = on_new, off_new
        if self.debug_rms:
            print(f"[CALIB] noise={noise_rms:.1f}, on={on_new:.1f}, off={off_new:.1f}")

    def _loop(self):
        state = "waiting_voice" if self.require_voice_first else "recording"
        silence_started_at: float | None = None

        if self.auto_calibrate:
            self._calibrate_thresholds(deadline=time.monotonic() + self.calib_max_time)

        with open(self.outfile, "wb") as f:
            while self._running.is_set():
                try:
                    data = self._q.get(timeout=0.5)
                except queue.Empty:
                    if state == "recording" and silence_started_at is not None:
                        if time.monotonic() - silence_started_at >= self.silence_duration:
                            break
                    continue

                f.write(data)

                rms = self._rms_int16(data)

                if state == "waiting_voice":
                    if rms >= self.voice_on_rms:
                        state = "recording"
                        silence_started_at = None
                    continue

                if rms >= self.voice_on_rms:
                    silence_started_at = None
                    continue

                if rms <= self.voice_off_rms:
                    if silence_started_at is None:
                        silence_started_at = time.monotonic()
                    elif time.monotonic() - silence_started_at >= self.silence_duration:
                        break
                else:
                    silence_started_at = None

        with self._mic_lock:
            try:
                if self._stream:
                    self._stream.stop()
                    self._stream.close()
            finally:
                self._stream = None
                self._running.clear()

        cb = self._on_done
        self._on_done = None
        if cb and self.outfile.exists() and self.outfile.stat().st_size > 0:
            try:
                cb(self.outfile)
            except Exception:
                pass