FROM python:3.11-slim

# Установка системных библиотек для браузеров
RUN apt-get update && apt-get install -y \
    curl unzip libnss3 libatk1.0-0 libatk-bridge2.0-0 libxss1 libasound2 \
    libx11-xcb1 libxcb-dri3-0 libxcomposite1 libxcursor1 libxdamage1 \
    libxrandr2 libxinerama1 libgbm1 libxext6 libxfixes3 libxrender1 \
    libfontconfig1 libgtk-3-0 && rm -rf /var/lib/apt/lists/*

# Создание рабочей папки
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка браузеров Playwright
RUN playwright install chromium --with-deps

# Копируем остальной код
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]