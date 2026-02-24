from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logger import logger, setup_logging
from app.db.session import async_session_maker, create_tables
from app.test_data.load_data import seed_admin_and_products


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    import app.models.batches  # noqa: F401

    if settings.ENV == "production" and (
        not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32
    ):
        raise ValueError(
            "В production задайте SECRET_KEY длиной не менее 32 символов"
            " в .env"
        )
    logger.info("🔄 Запуск PillStore...")
    await create_tables()

    if not settings.TESTING:
        async with async_session_maker() as db:
            await seed_admin_and_products(db)
        logger.info("🚀 База данных готова!")
    yield
