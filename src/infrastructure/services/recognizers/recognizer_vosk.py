import queue
import sys
import json
import threading
import sounddevice as sd
from vosk import Model, KaldiRecognizer

from pathlib import Path

MODEL_PATH = "vosk-model-small-ru-0.22"
BLOCKSIZE = 8000
DTYPE = "int16"
CHANNELS = 1


def get_input_device_index():
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            print(f"✔️ Найдено входное устройство: {dev['name']} (index {idx})")
            return idx
    raise RuntimeError("❌ Нет доступного входного аудиоустройства.")


DEVICE_INDEX = get_input_device_index()
SAMPLERATE = int(sd.query_devices(DEVICE_INDEX)["default_samplerate"])
print(sd.query_devices())


class VoiceStreamRecognizer:
    """
    Стриминговый распознаватель речи с паузой/возобновлением и коллбэком команд.
    """

    def __init__(self, model_path: str = MODEL_PATH, samplerate: int = SAMPLERATE,
                 device_index: int = DEVICE_INDEX):
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, samplerate)

        self.samplerate = samplerate
        self.device_index = device_index

        self._audio_q: queue.Queue[bytes] = queue.Queue()
        self._running = threading.Event()
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream: sd.RawInputStream | None = None

        self._on_command = None  # callable(str) -> None

    # ===== Публичные API =====
    def start(self, on_command):
        """
        Запускает прослушивание и стрим-обработку.
        :param on_command: функция-коллбэк, принимающая распознанный текст (str)
        """
        if self._running.is_set():
            return
        self._on_command = on_command
        self._running.set()
        self._paused.clear()

        # аудио-стрим
        self._stream = sd.RawInputStream(
            samplerate=self.samplerate,
            blocksize=BLOCKSIZE,
            dtype=DTYPE,
            channels=CHANNELS,
            device=self.device_index,
            callback=self._audio_callback,
        )
        self._stream.start()

        # воркер обработки
        self._thread = threading.Thread(target=self._loop, name="_vosk-loop", daemon=True)
        self._thread.start()
        print(f"▶️ Стрим запущен: device={self.device_index}, rate={self.samplerate}")

    def pause(self):
        """Приостановить обработку (микрофон слушает, но результаты игнорируются)."""
        if not self._paused.is_set():
            self._paused.set()
            self._reset_recognizer()
            print("⏸️ Прослушивание поставлено на паузу")

    def resume(self):
        """Возобновить обработку."""
        if self._paused.is_set():
            self._paused.clear()
            self._reset_recognizer()
            print("▶️ Прослушивание возобновлено")

    def stop(self):
        """Остановить обработку и закрыть ресурсы."""
        if not self._running.is_set():
            return
        self._running.clear()
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        # Дренируем очередь чтобы поток завершился
        try:
            while not self._audio_q.empty():
                self._audio_q.get_nowait()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        print("⏹️ Стрим остановлен")

    # ===== Внутреннее =====
    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"[AudioStatus] {status}", file=sys.stderr)
        self._audio_q.put(bytes(indata))

    def _loop(self):
        while self._running.is_set():
            data = self._audio_q.get()
            if not self._running.is_set():
                break

            if self._paused.is_set():
                # В паузе — не кормим распознаватель, просто пропускаем буфер
                continue

            if self.recognizer.AcceptWaveform(data):
                try:
                    result = json.loads(self.recognizer.Result() or "{}")
                except json.JSONDecodeError:
                    continue

                text = (result.get("text") or "").strip().lower()
                if not text:
                    continue

                # Коллбэк на каждую завершённую фразу
                if self._on_command:
                    try:
                        self._on_command(text)
                    except Exception as e:
                        print(f"[on_command error] {e}", file=sys.stderr)
            else:
                # Можно читать partial при необходимости:
                # partial = json.loads(self.recognizer.PartialResult()).get("partial", "")
                pass

    def _reset_recognizer(self):
        """Сброс распознавателя (сбрасывает внутренний буфер Vosk)."""
        self.recognizer = KaldiRecognizer(self.model, self.samplerate)
