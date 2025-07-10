import queue
import sys
import sounddevice as sd
import json
from vosk import Model, KaldiRecognizer

# === Конфигурация ===
MODEL_PATH = "src/infrastructure/services/recognizers/vosk/src/vosk-model-small-ru-0.22"
TRIGGER_WORD = "вася"  # ключевое слово для активации, всегда в lower-case

# Настройки звука — подбираем автоматически
DEVICE_INDEX = 2  # USB микрофон
SAMPLERATE = int(sd.query_devices(DEVICE_INDEX, 'input')['default_samplerate'])

# === Очередь аудио ===
q = queue.Queue()

# === Загрузка модели ===
print(f"Используем модель: {MODEL_PATH}")
print(f"Input device index: {DEVICE_INDEX}, samplerate: {SAMPLERATE}")

model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLERATE)

# === Аудио callback ===
def callback(indata, frames, time, status):
    if status:
        print(f"[AudioStatus] {status}", file=sys.stderr)
    q.put(bytes(indata))


def main():
    print(f"🎙️ Голосовой ассистент запущен. Жду ключевое слово: '{TRIGGER_WORD}'")

    triggered = False

    with sd.RawInputStream(
        samplerate=SAMPLERATE,
        blocksize=8000,
        dtype='int16',
        channels=1,
        device=DEVICE_INDEX,
        callback=callback
    ):
        while True:
            data = q.get()
            if recognizer.AcceptWaveform(data):
                # Используй безопасный json.loads вместо eval
                result_json = json.loads(recognizer.Result())
                text = result_json.get("text", "").strip().lower()

                if not text:
                    continue

                print(f"[Распознано] {text}")

                if not triggered:
                    if TRIGGER_WORD in text:
                        triggered = True
                        print(f"✅ Ключевое слово '{TRIGGER_WORD}' обнаружено.")
                        print("⏳ Начинаю слушать команду...")
                else:
                    print(f"🗣️ Команда: {text}")
                    triggered = False
                    print(f"🔁 Ожидание ключевого слова: '{TRIGGER_WORD}'")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🚫 Ассистент остановлен пользователем.")
    except Exception as e:
        print(f"[Ошибка] {e}")