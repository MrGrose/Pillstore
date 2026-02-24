# Тестовое пространство PillStore

## Изоляция от production

- При запуске тестов выставляется `TESTING=1` и БД подменяется на `*_test` (по умолчанию `pillstore_test`).
- Сид данных (seed) в lifespan не выполняется в тестовом режиме.
- Тестовая БД **создаётся автоматически** при первом запуске (подключение к `postgres`, затем `CREATE DATABASE`). Если сервер недоступен или нет прав — тесты будут пропущены с подсказкой.
- Либо создайте БД вручную: `createdb pillstore_test` или в Docker: `docker compose exec postgres createdb -U postgres pillstore_test`.

## Запуск

Из папки **app/tests/** (есть свой `Makefile`):

```bash
cd app/tests
make test            # все тесты
make test-unit       # только unit
make test-api        # только API
make test-integration # интеграция
make test-load       # нагрузочные
make test-cov        # тесты + отчёт покрытия
make help            # список целей
```

Либо из корня **pillstore/** напрямую через pytest:

```bash
PYTHONPATH=. poetry run pytest app/tests/ -v
PYTHONPATH=. poetry run pytest app/tests/ --cov=app --cov-report=term-missing
```

## Структура

- **unit/** — CRUD (batch_crud), сервисы (admin_service, order_service).
- **api/** — FastAPI endpoints (products, admin), авторизация.
- **integration/** — полный сценарий партии → заказ → оплата; проверка схемы БД.
- **load/** — параллельные запросы к /health и /api/v2/products.

## Покрытия

- 90%+ бизнес-логика (товары, партии).
- 80%+ API endpoints.
- 100% критичные сценарии: добавление партий, учёт остатков, FIFO.
