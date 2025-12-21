# Базовый образ на основе Python 3.13.2
FROM python:3.14.2-slim

# Установка рабочей директории внутри контейнера
WORKDIR /app

# Копирование файла зависимостей в контейнер
COPY requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода приложения в контейнер
COPY tuya_exporter.py .

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD /bin/bash -c "timeout 2 bash -c '</dev/tcp/localhost/8757'" || exit 1

# Команда для запуска приложения
CMD ["python", "-u", "tuya_exporter.py"]