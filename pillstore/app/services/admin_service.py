from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud.products_crud import CrudProduct
from app.db_crud.order_crud import CrudOrder

from app.models.orders import Order
from app.models.users import User
from app.models.products import Product
from app.db_crud.user_crud import CrudUser
from app.db_crud.admin_crud import CrudAdmin

from app.services.utils import remove_product_image, save_product_image
from app.schemas.product import ProductCreate, ProductUpdate
from app.db_crud.category_crud import CrudCategory
from app.models.categories import Category

from app.exceptions.handlers import (
    OrderNotFoundError,
    ProductNotFoundError,
    BusinessError,
)


class AdminService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.admin_crud = CrudAdmin(session=session)
        self.user_crud = CrudUser(session=session, model=User)
        self.order_crud = CrudOrder(session=session, model=Order)
        self.product_crud = CrudProduct(session=session, model=Product)
        self.category_crud = CrudCategory(session=session, model=Category)

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
            "orders": await self.order_crud.get_orders_list(status_filter),
        }

    async def order_status_admin(self, order_id: int, new_status: str) -> None:
        order = await self.order_crud.get_order(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        if new_status not in ["pending", "paid", "transit"]:
            raise BusinessError("Заказ", "Неверный статус")

        order.status = new_status
        await self.session.commit()

    async def remove_order_admin(self, order_id: int) -> None:
        order = await self.order_crud.get_order(order_id, load_products=True)
        if not order:
            raise OrderNotFoundError(order_id)

        for item in order.items:
            if item.product:
                item.product.stock += item.quantity

        await self.session.delete(order)
        await self.session.commit()
        for item in order.items:
            if item.product:
                await self.session.refresh(item.product, ["stock"])

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
    ) -> tuple[str, str]:
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

        return f"ID {product.id} Товар {product.name} создан", "success"
