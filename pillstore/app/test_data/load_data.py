import json
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.products import import_products
from app.core.auth_utils import hash_password
from app.core.logger import logger
from app.db_crud.batch_crud import CrudBatch
from app.db_crud.user_crud import CrudUser
from app.models.products import Product
from app.models.users import User as UserModel
from app.schemas.product import ProductImportList

json_path = "/app/app/test_data/products.json"

SEED_BATCHES = [
    {"quantity": 4, "expiry_date": "2026-06-01"},
    {"quantity": 3, "expiry_date": "2026-12-01"},
    {"quantity": 3, "expiry_date": "2027-06-01"},
]

SEED_COST_RATIO = 0.5


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

        batch_crud = CrudBatch(db)
        rows = await db.execute(
            select(Product).order_by(Product.id.asc()).limit(10)
        )
        added = 0
        for product in rows.scalars().all():
            existing = await batch_crud.get_batches_by_product(product.id)
            if existing:
                continue
            product.cost = float(product.price) * SEED_COST_RATIO
            product.stock = 0
            await db.flush()
            for batch in SEED_BATCHES:
                await batch_crud.add_batch(
                    product_id=product.id,
                    quantity=batch["quantity"],
                    expiry_date=batch["expiry_date"],
                    batch_code=None,
                )
            added += 1
        await db.commit()
        if added:
            logger.info(
                f"✅ Партии по 10 шт (сроки 2026-06, 2026-12, 2027-06) - {added} товаров"
            )
