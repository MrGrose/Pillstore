# PillStore - FastAPI E-commerce

Полнофункциональное веб-приложение интернет-магазина БАДов на FastAPI с PostgreSQL, аутентификацией, админ-панелью, корзиной, заказами, скрейпером iHerb и Telegram-ботом с Mini App.

## Основные возможности

### Аутентификация и пользователи
- Регистрация и вход с JWT токенами
- Роли пользователей: `buyer` (покупатель) и `seller` (продавец)
- Управление профилем пользователя
- Защищенные эндпоинты с проверкой прав доступа

### Каталог товаров
- Полнотекстовый поиск на русском и английском языках
- Пагинация и фильтрация по категориям
- Детальные страницы товаров с изображениями
- Категории товаров с иерархической структурой

### Корзина покупок
- Добавление, изменение количества и удаление товаров
- Сессионное хранение корзины
- API для интеграции с фронтендом

### Система заказов
- Оформление заказов с корзины
- Статусы заказов: `pending`, `paid`, `transit`, `delivered`, `cancelled`
- История заказов для пользователей
- Управление заказами для администраторов

### Админ-панель
- CRUD операции для товаров, категорий, пользователей и заказов
- Управление складскими остатками
- Смена статусов заказов, удаление заказов/товаров

### Импорт товаров
- Скрейпер iHerb с использованием CloudScraper для обхода защиты
- Автоматический перевод названий и описаний товаров
- Парсинг цен, изображений и характеристик
- Пакетный импорт товаров в каталог

### Telegram-бот
- Привязка аккаунта по email (проверка через API)
- Регистрация в боте (email + пароль) с последующей привязкой
- Мини-приложение магазина (Web App): каталог, корзина, оформление заказа
- Команды: `/start` (приветствие и привязка), `/help`

### API
- RESTful API с версионированием (v2)
- Swagger документация (автогенерация)
- Healthcheck эндпоинты для мониторинга
- Stock API для проверки наличия товаров

## Технологический стек

### Backend
- **FastAPI 0.121.3** - современный async веб-фреймворк
- **SQLAlchemy 2.0** - ORM для работы с базой данных
- **Alembic 1.17** - миграции базы данных
- **Pydantic 2.12** - валидация данных и схемы
- **JWT** - аутентификация с PyJWT
- **BCrypt** - хеширование паролей

### База данных
- **PostgreSQL 17** - основная реляционная БД
- **Asyncpg** - асинхронный драйвер PostgreSQL
- **Alembic** - управление миграциями

### Инфраструктура
- **Docker & Docker Compose** - контейнеризация
- **Poetry** - управление зависимостями Python
- **Uvicorn** - ASGI сервер

### Telegram-бот (отдельное приложение)
- **Aiogram 3.x** - асинхронный фреймворк для Telegram Bot API
- **Aiohttp** - запросы к API PillStore

### Вспомогательные библиотеки
- **Jinja2** - шаблонизация HTML
- **Aiohttp** - асинхронные HTTP запросы
- **CloudScraper** - обход защиты от скрейпинга
- **Googletrans/Deep Translator** - перевод контента
- **BeautifulSoup4/LXML** - парсинг HTML

### Качество кода
- **Ruff** - линтинг и форматирование
- **Black** - автоматическое форматирование кода
- **Flake8** - проверка стиля кода

## Структура проекта

```
pillstore/
├── Makefile                 # Команды: make up, make run, make lint, make migrate …
├── alembic.ini              # Конфигурация Alembic
├── docker-compose.yml       # Docker Compose (db, api)
├── Dockerfile               # Образ приложения
├── pyproject.toml           # Зависимости Poetry
├── media/                   # Загружаемые файлы
├── static/                  # Статические файлы (CSS, JS)
├── templates/               # Jinja2 HTML шаблоны
├── bot/                     # Telegram-бот (отдельный Poetry-проект)
│   ├── main.py              # Точка входа бота (polling)
│   ├── config.py            # PILLSTORE_BOT_TOKEN, API URL, Mini App URL
│   ├── handlers.py          # Обработчики /start, /help, привязка по email
│   ├── api_client.py        # Клиент API (check-email, link-telegram, mini-app-token)
│   └── pyproject.toml       # Зависимости: aiogram, aiohttp, python-dotenv
└── app/                     # Основной код приложения
    ├── main.py             # Точка входа FastAPI
    ├── core/
    │   ├── config.py
    │   ├── deps.py
    │   ├── security.py
    │   ├── logger.py
    │   ├── auth_utils.py
    │   └── init.py         # lifespan, seed данных при старте
    ├── db/                 # Работа с базой данных
    │   ├── base.py         # Базовый класс моделей
    │   └── session.py      # Сессии SQLAlchemy
    ├── db_crud/
    │   ├── base.py
    │   ├── products_crud.py
    │   ├── cart_crud.py
    │   ├── order_crud.py
    │   ├── user_crud.py
    │   ├── category_crud.py
    │   └── admin_crud.py
    ├── models/             # SQLAlchemy модели
    │   ├── users.py        # Пользователи
    │   ├── products.py     # Товары
    │   ├── categories.py   # Категории
    │   ├── cart_items.py   # Элементы корзины
    │   ├── orders.py       # Заказы
    │   └── associations.py # Ассоциативные таблицы
    ├── schemas/            # Pydantic схемы
    │   ├── auth.py
    │   ├── product.py
    │   ├── order.py
    │   ├── cart.py
    │   └── category.py
    ├── routers/            # Основные роутеры
    │   ├── auth.py         # Аутентификация
    │   ├── products.py     # Товары
    │   ├── orders.py       # Заказы
    │   ├── admin.py        # Админ-панель
    │   ├── profile.py      # Профиль
    │   ├── scraper.py      # Скрейпер
    │   └── errors.py       # Обработка ошибок
    ├── api/                # API v2
    │   └── v2/
    │       ├── products.py
    │       ├── categories.py
    │       ├── auth.py
    │       ├── cart.py
    │       ├── orders.py
    │       ├── profile.py
    │       └── admin.py
    ├── services/           # Бизнес-логика
    │   ├── admin_service.py
    │   ├── cart.py
    │   ├── cart_service.py
    │   ├── category_service.py
    │   ├── order_service.py
    │   ├── product_service.py
    │   ├── profile_service.py
    │   └── user_service.py
    ├── exceptions/
    │   └── handlers.py
    ├── migrations/
    │   └── versions/
    ├── test_data/
    │   └── load_data.py
    └── utils/
        ├── utils.py
        └── iherb_scraper.py
```

## Быстрый старт

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd pillstore
```

### 2. Настройка окружения
Создайте в папке **pillstore/** файл `.env`:

```env
# База данных (для Docker DATABASE_URL с хостом db; без Docker - session.py соберёт URL из POSTGRES_* и localhost:POSTGRES_PORT)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=pillstore_db
POSTGRES_PORT=5434
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/pillstore_db

# Окружение (production - включает HTTPS redirect в main.py)
ENV=development

# JWT (обязательно свой ключ в production)
SECRET_KEY=ваш-длинный-секретный-ключ

# Mini App и Telegram-бот (опционально)
# TELEGRAM_BOT_TOKEN=...           # Токен бота для проверки initData Mini App (в API)
# PILLSTORE_BOT_TOKEN=123:ABC...   # Тот же токен для запуска бота (в .env бота)
# PILLSTORE_API_URL=http://localhost:8000
# PILLSTORE_MINI_APP_URL=          # Публичный URL для Mini App (если отличается от API)
# PILLSTORE_SITE_URL=              # URL сайта для ссылки «Перейти на сайт»
```

Скрейпер iHerb не использует переменные окружения: базовый URL и настройки заданы в коде (`app/utils/iherb_scraper.py`).

### 3. Запуск с Docker (рекомендуется)
Из папки **pillstore/**:
```bash
cd pillstore
make up          # Запуск БД и API, вывод логов
make migrate     # Применить миграции (после первого up)
```
Вручную: `docker compose up -d --build`, затем `docker compose exec api poetry run alembic upgrade head`.

Тестовые данные (админ + товары из `test_data/products.json`) подгружаются при старте контейнера (lifespan).

### 4. Запуск без Docker
Из папки **pillstore/** (нужна PostgreSQL):
```bash
cd pillstore
make install         # poetry install
make migrate-local   # alembic upgrade head
make run             # uvicorn с --reload
```

### 5. Запуск Telegram-бота (опционально)
Бот работает как отдельное приложение и обращается к API по HTTP. Запуск из папки **pillstore/bot/**:

```bash
cd pillstore/bot
poetry install
# В .env в pillstore/ или в bot/ задайте: PILLSTORE_BOT_TOKEN, PILLSTORE_API_URL
poetry run python main.py
```

Переменные: `PILLSTORE_BOT_TOKEN` (обязательно), `PILLSTORE_API_URL` (по умолчанию http://localhost:8000), при необходимости `PILLSTORE_MINI_APP_URL` и `PILLSTORE_SITE_URL`. Для Mini App в Telegram нужен HTTPS (или туннель ngrok и т.п.).

### 6. Доступ к приложению
- **Главная страница**: http://localhost:8000/
- **Swagger документация**: http://localhost:8000/docs
- **ReDoc документация**: http://localhost:8000/redoc
- **Админ-панель**: http://localhost:8000/admin
- **Healthcheck**: http://localhost:8000/health

## Основные эндпоинты

### Публичные (HTML)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/` | Редирект на /products |
| GET | `/products` | Каталог товаров с пагинацией и поиском |
| GET | `/products/{product_id}` | Карточка товара |
| GET | `/products/api/stock/{product_id}` | Остаток товара (JSON) |
| GET | `/auth/` | Страница входа |
| POST | `/auth/login` | Вход |
| GET | `/auth/register` | Страница регистрации |
| POST | `/auth/register` | Регистрация |
| GET | `/auth/reset-password` | Форма сброса пароля |
| POST | `/auth/reset-password` | Сброс пароля |
| GET | `/mini` | Mini App магазина (Telegram Web App, параметр `t` - токен) |
| GET | `/health` | Healthcheck |

### Защищённые HTML (требуют аутентификации)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/profile/` | Профиль пользователя |
| GET | `/orders/cart` | Страница корзины |
| POST | `/orders/cart/remove/{item_id}` | Удалить позицию из корзины |
| POST | `/orders/cart/api/add` | Добавить в корзину (JSON) |
| POST | `/orders/cart/api/set` | Изменить количество (JSON) |
| POST | `/orders/checkout` | Оформление заказа из корзины |
| GET | `/orders/payment/{order_id}` | Страница оплаты заказа |
| POST | `/orders/{order_id}/confirm` | Подтвердить оплату |
| GET | `/orders/{order_id}` | Детали заказа |
| POST | `/orders/{order_id}/items/` | Добавить товар в заказ |
| POST | `/orders/{order_id}/items/{item_id}/return` | Вернуть позицию на склад |

### Админ HTML
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/admin` | Админ-панель (вкладки: dashboard, products, users, orders) |
| GET | `/admin/products/new` | Форма создания товара |
| POST | `/admin/products` | Создать товар |
| GET | `/admin/products/{id}/edit` | Форма редактирования товара |
| POST | `/admin/products/{id}` | Обновить товар |
| POST | `/admin/products/{id}/delete` | Удалить товар |
| POST | `/admin/products/iherb-import` | Импорт с iHerb (форма) |
| POST | `/admin/orders/{id}/status` | Изменить статус заказа |
| POST | `/admin/orders/{id}/delete` | Удалить заказ |
| GET | `/admin/users/new` | Форма создания пользователя |
| POST | `/admin/users/new` | Создать пользователя |
| GET | `/admin/users/{id}/edit` | Форма редактирования пользователя |
| POST | `/admin/users/{id}` | Обновить пользователя |
| POST | `/admin/users/{id}/delete` | Удалить пользователя |
| GET | `/access-denied` | Доступ запрещён |
| GET | `/admin/error-404` | Ошибка 404 (админ) |
| GET | `/admin/error-400` | Ошибка 400 (админ) |

### API v2 (JSON, префикс `/api/v2`)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/products` | Список товаров (пагинация) |
| GET | `/products/{id}` | Детали товара |
| GET | `/products/stock/{id}` | Остаток и доступность |
| POST | `/products` | Создать товар (seller) |
| PUT | `/products/{id}` | Обновить товар |
| DELETE | `/products/{id}` | Деактивировать (soft) |
| DELETE | `/products/{id}/hard` | Удалить из БД (hard) |
| POST | `/import` | Импорт товаров из JSON |
| GET | `/categories` | Дерево категорий |
| GET | `/categories/flat` | Плоский список категорий |
| GET | `/categories/{id}` | Категория по id |
| GET | `/categories/{id}/with-children` | Категория с потомками |
| POST | `/categories` | Создать категорию |
| PUT | `/categories/{id}` | Обновить категорию |
| DELETE | `/categories/{id}` | Деактивировать категорию |
| POST | `/auth/register` | Регистрация |
| POST | `/auth/login` | Вход (Form) |
| GET | `/auth/check-email` | Проверка существования email (для бота) |
| POST | `/auth/link-telegram` | Привязка Telegram ID к аккаунту |
| POST | `/auth/mini-app-token` | Токен для Mini App (заголовок X-Telegram-User-Id) |
| POST | `/token` | JWT (OAuth2 form для Swagger) |
| GET | `/users/me` | Текущий пользователь |
| PUT | `/users/me` | Обновить профиль |
| DELETE | `/users/me` | Деактивировать себя |
| POST | `/auth/logout` | Выход |
| POST | `/auth/reset-password/request` | Запрос сброса пароля |
| POST | `/auth/reset-password/confirm` | Подтверждение сброса |
| GET | `/cart` | Корзина |
| GET | `/cart/count` | Количество позиций в корзине |
| POST | `/cart/items` | Добавить в корзину |
| PUT | `/cart/items/{item_id}` | Изменить количество |
| DELETE | `/cart/items/{item_id}` | Удалить из корзины |
| DELETE | `/cart` | Очистить корзину |
| GET | `/orders` | Список заказов (пагинация) |
| POST | `/orders/checkout` | Оформить заказ из корзины |
| GET | `/orders/{id}` | Детали заказа |
| PUT | `/orders/{id}/cancel` | Отменить заказ |
| POST | `/orders/{id}/confirm` | Подтвердить оплату |
| GET | `/orders/payment/{id}` | Данные для страницы оплаты |
| POST | `/orders/{id}/items/{item_id}/return` | Вернуть позицию на склад |
| POST | `/orders/{id}/items` | Добавить товар в заказ |
| GET | `/profile` | Профиль (заказы пользователя) |
| GET | `/admin/stats` | Статистика (admin) |
| GET | `/admin/users` | Список пользователей |
| POST | `/admin/users` | Создать пользователя |
| PUT | `/admin/users/{id}` | Обновить пользователя |
| DELETE | `/admin/users/{id}` | Удалить пользователя |
| GET | `/admin/orders` | Список заказов |
| PUT | `/admin/orders/{id}/status` | Изменить статус заказа |
| DELETE | `/admin/orders/{id}` | Удалить заказ |
| GET | `/admin/products` | Список товаров (пагинация) |
| POST | `/admin/products` | Создать товар |
| PUT | `/admin/products/{id}` | Обновить товар |
| DELETE | `/admin/products/{id}` | Удалить товар |

## Разработка

Команды выполняются из папки **pillstore/** (где лежат `Makefile`, `pyproject.toml`, `app/`). Telegram-бот - отдельный Poetry-проект в `pillstore/bot/`, см. раздел «Запуск Telegram-бота».

### Makefile

| Команда | Описание |
|---------|----------|
| `make up` | Запустить БД и API в Docker, показать логи |
| `make build` | Собрать и запустить контейнеры |
| `make logs` | Логи API |
| `make logs-db` | Логи БД |
| `make stop` | Остановить контейнеры |
| `make down` | Остановить и удалить тома |
| `make rest` | Перезапустить API |
| `make migrate` | Применить миграции в контейнере |
| `make shell` | Bash в контейнере API |
| `make install` | poetry install |
| `make migrate-local` | Применить миграции локально |
| `make run` | Запуск сервера локально (uvicorn --reload) |
| `make lint` | flake8 app |
| `make format` | black app |
| `make test` | pytest |

Миграции вручную: `poetry run alembic revision --autogenerate -m "описание"`, `poetry run alembic upgrade head`, `poetry run alembic downgrade -1`.

Тестовые данные: при старте (lifespan) создаётся админ **admin@admin.ru** / `12345678` и при наличии `app/test_data/products.json` - импорт товаров. Тестов и pytest-cov в проекте пока нет.

## Модели данных

### Основные сущности:
- **User** - пользователи системы с ролями buyer/seller
- **Product** - товары с ценами, описаниями и изображениями
- **Category** - категории товаров с иерархией
- **CartItem** - элементы корзины пользователя
- **Order** - заказы с статусами и историей
- **OrderItem** - товары в заказе

## Безопасность

- JWT аутентификация с access токенами; все админские маршруты (HTML и API) защищены ролью seller
- Хеширование паролей с BCrypt
- CORS и список доверенных хостов задаются через .env (ALLOWED_ORIGINS, ALLOWED_HOSTS)
- TrustedHostMiddleware и HTTPS-редирект в production
- Куки: httponly, в production - secure и samesite=lax
- В production обязателен SECRET_KEY не короче 32 символов (проверка при старте)
- SQL-запросы в production не логируются (echo=False)
- Валидация входных данных с Pydantic

### Развёртывание на сервере

В `.env` на сервере задайте:

- `ENV=production`
- `SECRET_KEY=<длинный случайный ключ ≥32 символов>`
- `DATABASE_URL=postgresql+asyncpg://...` (доступ к БД с сервера)
- `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com` - ваши домены
- `ALLOWED_ORIGINS=https://yourdomain.com,...` - разрешённые источники для CORS (если есть отдельный фронт)

Рекомендуется: прокси (nginx) с HTTPS и проксирование на uvicorn, отключить `--reload` в production.

## Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функциональности (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add some amazing feature'`)
4. Отправьте в форк (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## Лицензия

Этот проект лицензирован под MIT License - смотрите файл LICENSE для деталей.


**PillStore** - современный интернет-магазин БАДов с полным циклом от скрейпинга товаров до оформления заказов и администрирования.