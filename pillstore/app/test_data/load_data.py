import json
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.products import import_products
from app.core.auth_utils import hash_password
from app.core.logger import logger
from app.db_crud.user_crud import CrudUser
from app.models.users import User as UserModel
from app.schemas.product import ProductImportList


json_path = "/app/app/test_data/products.json"


async def seed_admin_and_products(db: AsyncSession):
    crud_user = CrudUser(db, UserModel)
    admin = await crud_user.check_user_email("admin@admin.ru")
    if not admin:
        admin_data = {
            "email": "admin@admin.ru",
            "hashed_password": hash_password("12345678"),
            "is_active": True,
            "role": "seller",
        }
        admin = await crud_user.create(admin_data)
        logger.info("✅ Админ создан!")

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            import_data = ProductImportList(**json.load(f))

        result = await import_products(import_data, db=db, bypass_auth=True)
        logger.info(f"✅ Импорт: {result}")
