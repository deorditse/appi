🔧 Архитектура

```text
[Микрофон]
    ↓
[ Vosk (локальное ASR) ]
    ↓
[ SQLite БД с командами ]
    ↓                  ↘
[ есть команда? ] → [ Выполнить ]  
         ↓
      [ нет ]
         ↓
[ Сохраняем аудио .wav ]
         ↓
[ Отправляем .wav через API на backend ]
         ↓
[ Получаем ответ ]
         ↓
[ Озвучиваем или обрабатываем ответ ]
```

____________

Локальный запуск

🔧 Шаг 1: Установка и окружение

```commandline
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### Установим зависимости

```commandline
sudo apt update
sudo apt install espeak python3-pyaudio -y
pip install vosk sounddevice requests
```


python3 src/infrastructure/services/recognizers/vosk/recognizer_vosk.py   



```commandline
git lfs install
git lfs track "src/infrastructure/services/recognizers/vosk/src/vosk-model-ru-0.42"
```
