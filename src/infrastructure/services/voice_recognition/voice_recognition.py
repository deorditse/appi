import queue
import sys
import json
import threading
import sounddevice as sd
from vosk import Model, KaldiRecognizer


def get_input_device_index():
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            print(f"✔️ Найдено входное устройство: {dev['name']} (index {idx})")
            return idx
    raise RuntimeError("❌ Нет доступного входного аудиоустройства.")


DEVICE_INDEX = get_input_device_index()
SAMPLERATE = int(sd.query_devices(DEVICE_INDEX)["default_samplerate"])


class VoiceStreamRecognizer:
    """
    Минимальный вариант:
      - start(on_command) запускает микрофон и распознавание
      - pause(True) приостанавливает обработку (но микрофон остаётся открыт)
      - pause(False) возобновляет обработку
    """

    def __init__(self, model_path: str, samplerate: int = SAMPLERATE, device_index: int = DEVICE_INDEX,
                 blocksize: int = 8000, dtype: str = "int16", channels: int = 1):
        self.model = Model(str(model_path))
        self.recognizer = KaldiRecognizer(self.model, samplerate)

        self.samplerate = samplerate
        self.device_index = device_index
        self.blocksize = blocksize
        self.dtype = dtype
        self.channels = channels

        self._audio_q: queue.Queue[bytes] = queue.Queue()
        self._running = threading.Event()
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream: sd.RawInputStream | None = None
        self._on_command = None

    def start(self, on_command):
        """Запуск прослушивания и обработки."""
        if self._running.is_set():
            return
        self._on_command = on_command
        self._running.set()
        self._paused.clear()

        self._stream = sd.RawInputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype=self.dtype,
            channels=self.channels,
            device=self.device_index,
            callback=self._audio_callback,
        )
        self._stream.start()

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"▶️ Стрим запущен: device={self.device_index}, rate={self.samplerate}")

    def pause(self, flag: bool = True):
        """Управление паузой."""
        if flag:
            self._paused.set()
            self._reset_recognizer()
            self._stream.stop()
            print("⏸️ Распознавание приостановлено")
        else:
            self._paused.clear()
            self._reset_recognizer()
            self._stream.start()
            print("▶️ Распознавание возобновлено")

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
                continue

            if self.recognizer.AcceptWaveform(data):
                try:
                    result = json.loads(self.recognizer.Result() or "{}")
                except json.JSONDecodeError:
                    continue

                text = (result.get("text") or "").strip().lower()
                if text and self._on_command:
                    try:
                        self._on_command(text)
                    except Exception as e:
                        print(f"[on_command error] {e}", file=sys.stderr)

    def _reset_recognizer(self):
        self.recognizer = KaldiRecognizer(self.model, self.samplerate)
