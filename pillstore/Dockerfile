FROM python:3.12

WORKDIR /code

# 1. Зависимости (кешится)
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 2. Создаём структуру pillstore/app
RUN mkdir -p /code/pillstore

# 3. Копируем app в pillstore/app (НЕ в /code/app)
COPY ./app /code/pillstore/app
COPY ./static /code/static
COPY ./media /code/media
COPY ./alembic.ini /code/alembic.ini
COPY .env /code/.env


# pillstore.app.main:app — правильный импорт!
CMD ["uvicorn", "pillstore.app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
