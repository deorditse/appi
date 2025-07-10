import queue
import sys
import sounddevice as sd
from vosk import Model, KaldiRecognizer

print(sd.query_devices())
print("Default samplerate:", sd.query_devices(kind='input')['default_samplerate'])

# === Конфигурация ===
MODEL_PATH = "src/infrastructure/services/recognizers/vosk/src/vosk-model-small-ru-0.22"  # папка с распакованной моделью
TRIGGER_WORD = "Вася"  # ключевое слово для активации
SAMPLERATE = 16000
DEVICE_INDEX = 2  # индекс USB микрофон
# === Загрузка модели ===
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLERATE)

# === Очередь аудио ===
q = queue.Queue()


# === Аудио callback ===
def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))


def main():
    print(f"Голосовой ассистент запущен. Жду ключевое слово: '{TRIGGER_WORD}'")

    triggered = False

    # Открываем поток аудио
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
                result = recognizer.Result()
                text = eval(result)["text"].lower()
                print(f"Активация: '{text}'")
                if not triggered:
                    if TRIGGER_WORD in text:
                        triggered = True
                        print(f"Активация: '{TRIGGER_WORD}' обнаружено.")
                        print("Начинаю слушать фразу...")
                else:
                    if text.strip():
                        print(f"Распознано: {text}")
                        print("Ассистент снова ждёт ключевое слово.")
                        triggered = False


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nАссистент остановлен пользователем.")
    except Exception as e:
        print(str(e))
