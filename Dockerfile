
# Используем стабильный образ Python 3.15
FROM python:3.15-slim

# Запрещаем создание дополнительных .pyc-файлов
ENV PYTHONDONTWRITEBYTECODE=1

# Обеспечиваем вывод логов сразу в терминал
ENV PYTHONUNBUFFERED=1

# Создаём рабочую папку внутри контейнера
WORKDIR /app

# Создаём отдельного пользователя для запуска приложения
RUN groupadd --system appuser && \
    useradd --system --gid appuser --home-dir /app appuser

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем библиотеки Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY --chown=appuser:appuser app/ ./app/

# Запускаем приложение не от имени администратора
USER appuser

# Открываем порт приложения
EXPOSE 8000

# Проверяем работоспособность приложения
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# Команда запуска FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
