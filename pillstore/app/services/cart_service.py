from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud.cart_crud import CrudCart
from app.db_crud.order_crud import CrudOrder
from app.db_crud.products_crud import CrudProduct
from app.models.cart_items import CartItem
from app.models.orders import Order
from app.models.products import Product
from app.models.users import User

from app.schemas.product import ProductRead
from app.exceptions.handlers import (
    ProductNotFoundError,
    CartNotFoundError,
    BusinessError,
)


class CartService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudCart(session=session, model=CartItem)
        self.product_crud = CrudProduct(session=session, model=Product)
        self.order_crud = CrudOrder(session=session, model=Order)

    async def cart_count(self, user: User | None, products: list[ProductRead]) -> int:
        return await self.crud.cart_count(user, products)

    async def add_to_cart(self, user: User, product_id: int, quantity: int) -> dict:
        current_qty = await self.crud.get_cart_quantity(user.id, product_id)
        product = await self.product_crud.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        reserved = await self.order_crud.get_pending_reserved(product_id)
        available = (product.stock or 0) - reserved
        total_qty = current_qty + quantity

        if total_qty > available:
            can_add = max(0, available - current_qty)
            raise BusinessError(
                "Корзина",
                f"Недостаточно товара. Можно добавить ещё: {can_add} шт.",
            )

        await self.crud.add_or_update(user.id, product_id, total_qty)
        return {"cart_qty": total_qty}

    async def get_cart_page(self, current_user, ordered) -> tuple[CartItem, float]:
        cart_items = await self.crud.get_cart_items(current_user.id, ordered)
        total = sum(
            item.product.price * item.quantity for item in cart_items if item.product
        )
        return cart_items, total

    async def remove_cart_item_by_id(self, user_id: int, item_id: int) -> None:
        cart_item = await self.crud.get_cart_item_by_id(user_id, item_id)
        if not cart_item:
            raise CartNotFoundError(item_id)
        await self.session.delete(cart_item)
        await self.session.commit()

    async def update_item_quantity(
        self, user_id: int, item_id: int, quantity: int
    ) -> CartItem:
        cart_item = await self.crud.get_cart_item_by_id(user_id, item_id)
        if not cart_item:
            raise CartNotFoundError(item_id)
        product = await self.product_crud.get_by_id(cart_item.product_id)
        if not product:
            raise ProductNotFoundError(cart_item.product_id)
        reserved = await self.order_crud.get_pending_reserved(cart_item.product_id)
        available = (product.stock or 0) - reserved
        if available < quantity:
            raise BusinessError(
                "Корзина",
                f"Недостаточно товара на складе. Доступно: {available} шт.",
            )
        cart_item.quantity = quantity
        await self.session.commit()
        await self.session.refresh(cart_item)
        return cart_item

    async def clear_cart(self, user_id: int) -> None:
        await self.crud.delete_cart_by_user(user_id)
        await self.session.commit()

    async def get_cart_count(self, user_id: int) -> int:
        items = await self.crud.get_cart_items(user_id, ordered=False)
        return sum(item.quantity for item in items)

    async def add_or_set_cart_item(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
        add_mode: bool = False,
    ) -> int:
        product = await self.product_crud.get_product_active(product_id)
        return await self.cart_update_api(
            user_id, product_id, quantity, product, add_mode=add_mode
        )

    async def cart_update_api(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
        product: Product,
        add_mode: bool = False,
    ) -> int:
        cart_item = await self.crud.get_cart_item(user_id, product_id)

        if add_mode and cart_item:
            quantity += cart_item.quantity

        reserved = await self.order_crud.get_pending_reserved(product_id)
        available = (product.stock or 0) - reserved
        final_qty = min(quantity, available)

        if final_qty == 0:
            if cart_item:
                await self.session.delete(cart_item)
            await self.session.commit()
            return 0

        if cart_item:
            cart_item.quantity = final_qty
            cart_item.updated_at = datetime.now(timezone.utc)
        else:
            cart_item = CartItem(
                user_id=user_id, product_id=product_id, quantity=final_qty
            )
            self.session.add(cart_item)

        await self.session.commit()
        await self.session.refresh(cart_item)

        return cart_item.quantity
