from pathlib import Path

from src.infrastructure.services.recognizers.recognizer_vosk import VoiceStreamRecognizer
import threading
from commands import is_stop, is_pause, is_resume  # из блока выше


def main():
    SRC_DIR = Path(__file__).resolve().parents[1]  # .../src
    MODEL_DIR = SRC_DIR / "infrastructure/services/recognizers/vosk-model-small-ru-0.22"

    # ВАЖНО: передаём str
    vr = VoiceStreamRecognizer(model_path=str(MODEL_DIR))
    stop_event = threading.Event()

    def on_command(text: str):
        print(f"[Распознано] {text}")

        if is_stop(text):
            vr.stop()
            stop_event.set()  # аккуратно выходим из main
            return

        if is_pause(text):
            vr.pause()
            return

        if is_resume(text):
            vr.resume()
            return

        # --- здесь ваша бизнес-логика ---
        # route_command(text)
        # do_something(text)

    try:
        vr.start(on_command=on_command)
        # Держим процесс, пока не придёт «стоп»
        stop_event.wait()
    finally:
        vr.stop()


if __name__ == "__main__":
    main()
