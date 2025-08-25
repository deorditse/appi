# file: src/infrastructure/services/http/send_http.py

from pathlib import Path
import wave
import numpy as np
import sounddevice as sd


class SendHttp:
    def send_audio_file(self, path: Path):
        """Заглушка: вывести инфо о файле и воспроизвести его"""
        print(f"[REC] Готов файл: {path} ({path.stat().st_size} байт)")

        try:
            with wave.open(str(path), "rb") as wf:
                samplerate = wf.getframerate()
                channels = wf.getnchannels()
                frames = wf.readframes(wf.getnframes())

            data = np.frombuffer(frames, dtype=np.int16)
            if channels > 1:
                data = data.reshape(-1, channels)

            print(f"[PLAY] Воспроизведение {path.name} ...")
            sd.play(data, samplerate)
            sd.wait()
            print(f"[PLAY] Готово")
        except Exception as e:
            print(f"[ERROR] Не удалось воспроизвести {path}: {e}")
