# file: src/infrastructure/services/http/send_http.py

from pathlib import Path
import wave
import numpy as np
import sounddevice as sd


class SendHttp:
    def send_audio_file(self, path: Path, samplerate: int):
        """Заглушка: вывести инфо о файле и воспроизвести его"""
        print(f"[REC] Готов файл: {path} ({path.stat().st_size} байт)")

        try:

            with open(str(path), "rb") as f:
                raw = f.read()

            arr = np.frombuffer(raw, dtype=np.int16)
            sd.play(arr, samplerate=samplerate)
            sd.wait()

        except Exception as e:
            print(f"[ERROR] Не удалось воспроизвести {path}: {e}")
