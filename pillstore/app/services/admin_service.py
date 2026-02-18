from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud.admin_crud import CrudAdmin
from app.db_crud.batch_crud import CrudBatch
from app.db_crud.category_crud import CrudCategory
from app.db_crud.order_crud import CrudOrder
from app.db_crud.products_crud import CrudProduct
from app.db_crud.user_crud import CrudUser
from app.exceptions.handlers import (
    BusinessError,
    OrderNotFoundError,
    ProductNotFoundError,
)
from app.models.categories import Category
from app.models.orders import Order
from app.models.products import Product
from app.models.users import User
from app.schemas.product import ProductCreate, ProductUpdate
from app.utils.utils import remove_product_image, save_product_image


class AdminService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.admin_crud = CrudAdmin(session=session)
        self.user_crud = CrudUser(session=session, model=User)
        self.order_crud = CrudOrder(session=session, model=Order)
        self.product_crud = CrudProduct(session=session, model=Product)
        self.category_crud = CrudCategory(session=session, model=Category)
        self.batch_crud = CrudBatch(session)

    async def _user_order_counts(self, users: list[User]) -> dict[int, int]:
        user_order_counts = {}
        for user in users:
            count = await self.order_crud.get_user_order_counts(user)
            user_order_counts[user.id] = count
        return user_order_counts

    async def get_admin_page(self, status_filter: str | None) -> dict:
        if status_filter == "None":
            status_filter = None

        users = await self.user_crud.get_users()

        return {
            "stats": await self.admin_crud.dashboard_stats(),
            "products": await self.product_crud.get_all(True),
            "products_not_active": await self.product_crud.get_all(False),
            "user_order_counts": await self._user_order_counts(users),
            "users": users,
            "orders": await self.order_crud.get_orders_user_list(
                status_filter, load_items=False
            ),
        }

    async def order_status_admin(self, order_id: int, new_status: str) -> None:
        order = await self.order_crud.get_order(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        allowed = ("pending", "paid", "transit", "delivered", "cancelled")
        if new_status not in allowed:
            raise BusinessError("Заказ", "Неверный статус")

        order.status = new_status
        await self.session.commit()

    async def remove_order_admin(self, order_id: int) -> None:
        order = await self.order_crud.get_order(order_id, load_products=True)
        if not order:
            raise OrderNotFoundError(order_id)

        for item in order.items:
            await self.batch_crud.return_deductions_for_order_item(item)

        await self.session.delete(order)
        await self.session.commit()

    async def remove_product_admin(self, product_id: int) -> str:
        product = await self.product_crud.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        if product.image_url:
            remove_product_image(product.image_url)
        await self.product_crud.delete(product.id)

        return f"ID {product.id} Товар {product.name} удален"

    async def update_product_admin(
        self,
        product_id: int,
        data: ProductUpdate,
        category_ids: list[int],
        image: UploadFile | None = None,
    ) -> tuple[str, str]:
        product = await self.product_crud.update_product(product_id, data)
        if not product:
            raise ProductNotFoundError(product_id)
        if image and image.filename:
            if product.image_url:
                remove_product_image(product.image_url)
            product.image_url = await save_product_image(image)
            self.session.add(product)
            await self.session.commit()

        new_categories = await self.category_crud.get_by_ids(category_ids)
        product.categories = new_categories

        return f"ID {product.id} Товар {product.name} обновлен", "success"

    async def create_product_admin(
        self, data: ProductCreate, image: UploadFile | None = None
    ) -> tuple[str, Product]:
        product_data = data.model_dump(exclude={"image_url"})
        product = await self.product_crud.create(product_data)

        if data.image_url:
            product.image_url = data.image_url
        elif image and image.filename:
            product.image_url = await save_product_image(image)
        else:
            product.image_url = ""

        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return f"ID {product.id} Товар {product.name} создан", product

    async def get_stats(self) -> dict:
        return await self.admin_crud.dashboard_stats()

    async def get_orders_for_admin(self, status_filter: str | None = None) -> list:
        return await self.order_crud.get_orders_user_list(
            status_filter, load_items=True
        )

    async def get_products_for_admin_paginated(
        self,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        items, total = await self.product_crud.get_products_paginated(
            is_active=active_only, page=page, page_size=page_size
        )
        total_active = await self.product_crud.get_products_count(True)
        total_inactive = await self.product_crud.get_products_count(False)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_active": total_active,
            "total_inactive": total_inactive,
        }

    async def create_product_check_url(
        self, data: ProductCreate, image: UploadFile | None = None
    ) -> Product:
        if data.url:
            existing = await self.product_crud.get_by_url(data.url)
            if existing:
                raise BusinessError("Товар", "Товар с таким URL уже существует")
        _, product = await self.create_product_admin(data, image)
        return product

    async def get_product_by_id(self, product_id: int) -> Product | None:
        return await self.product_crud.get_by_id(product_id)

    async def get_batches_for_product(self, product_id: int) -> list:
        batches = await self.batch_crud.get_batches_by_product(
            product_id, order_by_expiry_asc=True
        )
        result = []
        for b in batches:
            if b.quantity <= 0:
                continue
            used = sum(d.quantity for d in b.deductions)
            result.append(
                {
                    "id": b.id,
                    "expiry_date": b.expiry_date,
                    "quantity": b.quantity,
                    "batch_code": b.batch_code,
                    "used": used,
                    "deductions": b.deductions,
                }
            )
        return result

    async def add_batch_admin(
        self,
        product_id: int,
        quantity: int,
        expiry_date: str | None = None,
    ) -> None:
        product = await self.product_crud.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        await self.batch_crud.add_batch(
            product_id=product_id,
            quantity=quantity,
            expiry_date=expiry_date,
            batch_code=None,
        )
        await self.session.commit()

    async def delete_batch_admin(self, product_id: int, batch_id: int) -> None:
        from app.models.batches import ProductBatch

        batch = await self.session.get(ProductBatch, batch_id)
        if not batch or batch.product_id != product_id:
            raise ProductNotFoundError(batch_id)
        await self.batch_crud.delete_batch(batch_id)
        await self.session.commit()
