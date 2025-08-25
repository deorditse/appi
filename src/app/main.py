import asyncio
import time
from pathlib import Path
import threading

from infrastructure.repositories.http.send import SendHttp
from infrastructure.services.voice_recording.voice_recording import VoiceRecording
from src.infrastructure.services.voice_recognition.voice_recognition import VoiceStreamRecognizer
from commands import is_pause, is_resume, is_start  # ваши функции

send_repository = SendHttp()


async def main():
    SRC_DIR = Path(__file__).resolve().parents[1]  # .../src
    MODEL_DIR = SRC_DIR / "infrastructure/services/voice_recognition/vosk-model-small-ru-0.22"

    # Важно: внутри вашего VoiceStreamRecognizer должны быть ТОЛЬКО start() и pause(flag)
    vr = VoiceStreamRecognizer(model_path=str(MODEL_DIR))

    recorder = VoiceRecording(samplerate=24000)

    recording_active = threading.Event()
    loop = asyncio.get_running_loop()

    def on_file_ready(path: Path):
        # Отправляем корутину в текущий loop (он запущен asyncio.run(main()))
        fut = asyncio.run_coroutine_threadsafe(
            send_repository.send_audio_file(path, samplerate=24000),
            loop
        )

        def _after_send(_):
            try:
                fut.result()  #
            except Exception as e:
                print(f"[SEND ERROR] {e}")
            vr.pause(False)
            recording_active.clear()

        fut.add_done_callback(_after_send)

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

    vr.start(on_command=on_command)
    # Держим событие, чтобы loop жил (или замените на свою логику завершения)
    await asyncio.Event().wait()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())  # ← вместо простого main()
