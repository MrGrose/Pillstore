from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest
import pytest_asyncio
import asyncpg
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


os.environ["TESTING"] = "1"
os.environ.setdefault("POSTGRES_DB", "pillstore_db")
if not os.environ["POSTGRES_DB"].endswith("_test"):
    os.environ["POSTGRES_DB"] = "pillstore_test"

from app.core.config import settings
from app.core.deps import get_db
from app.db.base import Base
from app.main import app


def _test_database_name() -> str:
    return urlparse(settings.database_url).path.lstrip("/") or "pillstore_test"


@pytest_asyncio.fixture
async def ensure_test_db():
    db_name = _test_database_name()
    conn = None
    try:
        conn = await asyncpg.connect(
            host=settings.POSTGRES_HOST,
            port=int(settings.POSTGRES_PORT),
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD or "",
            database="postgres",
        )
        await conn.execute(f'CREATE DATABASE "{db_name}"')
    except asyncpg.DuplicateDatabaseError:
        pass
    except Exception as e:
        pytest.skip(
            f"Не удалось создать тестовую БД {db_name}: {e}. "
            "Проверьте POSTGRES_* и что сервер доступен."
        )
    finally:
        if conn:
            await conn.close()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def test_engine(ensure_test_db):
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
def test_session_factory(test_engine):
    return async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )


@pytest_asyncio.fixture
async def db_session(test_engine):
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            session_factory = async_sessionmaker(
                bind=conn,
                expire_on_commit=False,
                class_=AsyncSession,
                join_transaction_mode="create_savepoint",
            )
            async with session_factory() as session:
                yield session
        finally:
            await trans.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seller_user(db_session):
    from uuid import uuid4
    from app.core.auth_utils import hash_password
    from app.db_crud.user_crud import CrudUser
    from app.models.users import User as UserModel

    email = f"seller-{uuid4().hex[:8]}@test.ru"
    crud = CrudUser(db_session, UserModel)
    user = await crud.create({
        "email": email,
        "hashed_password": hash_password("seller123"),
        "is_active": True,
        "role": "seller",
    })
    await db_session.commit()
    await db_session.refresh(user)
    user._test_email = email  # для seller_token
    return user


@pytest_asyncio.fixture
async def seller_token(client, db_session, seller_user):
    from app.services.user_service import UserService

    user_service = UserService(db_session)
    email = getattr(seller_user, "_test_email", seller_user.email)
    token = await user_service.authenticate_user(
        email=email, password="seller123"
    )
    return token


@pytest_asyncio.fixture
async def auth_client(client, seller_token):
    client.cookies.set("access_token", seller_token)
    return client
