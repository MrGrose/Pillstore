from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logger import logger
from app.db.session import async_session_maker, create_tables
from app.test_data.load_data import seed_admin_and_products


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models.batches  # noqa: F401
    logger.info("🔄 Запуск PillStore...")
    await create_tables()

    async with async_session_maker() as db:
        await seed_admin_and_products(db)

    logger.info("🚀 База данных готова!")
    yield
