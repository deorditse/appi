import time
from pathlib import Path
import threading

from infrastructure.services.voice_recording.voice_recording import VoiceRecording
from src.infrastructure.services.voice_recognition.voice_recognition import VoiceStreamRecognizer
from commands import is_pause, is_resume, is_start  # ваши функции


def main():
    SRC_DIR = Path(__file__).resolve().parents[1]  # .../src
    MODEL_DIR = SRC_DIR / "infrastructure/services/voice_recognition/vosk-model-small-ru-0.22"

    # Важно: внутри вашего VoiceStreamRecognizer должны быть ТОЛЬКО start() и pause(flag)
    vr = VoiceStreamRecognizer(model_path=str(MODEL_DIR))

    # Запись в отдельный WAV, старт — сразу, окончание — после 2 с тишины
    recorder = VoiceRecording(samplerate=vr.samplerate)

    stop_event = threading.Event()
    recording_active = threading.Event()

    def on_file_ready(path: Path):
        print(f"[REC] Готов файл: {path} ({path.stat().st_size} байт)")
        # TODO: отправка файла (HTTP/OpenAI/S3 и т.д.)

        time.sleep(0.08)
        vr.pause(False)
        recording_active.clear()

    def on_command(text: str):
        print(f"[Распознано] {text}")

        # Старт записи по ключевой фразе
        if is_start(text):
            if recording_active.is_set():
                return  # запись уже идёт
            print("[CMD] is_start → пауза распознавания и старт записи")
            recording_active.set()

            vr.pause(True)

            # если бывают конфликты на macOS при открытии второго потока,
            # можно добавить микропаузу: time.sleep(0.15)
            recorder.record_async(on_done=on_file_ready)
            return

        # Ручные команды (если нужны)
        if is_pause(text):
            print("[CMD] is_pause")
            vr.pause(True)
            return

        if is_resume(text):
            print("[CMD] is_resume")
            vr.pause(False)
            return

    try:
        vr.start(on_command=on_command)
        stop_event.wait()  # держим процесс
    finally:
        pass


if __name__ == "__main__":
    main()
