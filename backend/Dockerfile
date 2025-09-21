# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

# Рабочая директория
WORKDIR /app

# Системные зависимости для Chrome, Selenium и сборки некоторых пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    wget \
    curl \
    gnupg \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Указываем путь к драйверу
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Копируем только requirements для кэширования слоев
COPY requirements.txt .

# Используем pip cache для ускорения повторных сборок
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# Копируем весь код
COPY . .

# Стандартная команда запуска
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
