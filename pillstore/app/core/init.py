from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.db.session import create_tables, async_session_maker
from app.test_data.load_data import seed_admin_and_products
from app.core.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🔄 Запуск PillStore...")
    await create_tables()

    async with async_session_maker() as db:
        await seed_admin_and_products(db)

    logger.info("🚀 База данных готова!")
    yield
