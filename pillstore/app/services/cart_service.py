from datetime import datetime, timezone
from fastapi import HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud.cart_crud import CrudCart
from app.db_crud.products_crud import CrudProduct

from app.models.cart_items import CartItem
from app.models.users import User
from app.models.products import Product

from app.schemas.product import ProductRead


class CartService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudCart(session=session, model=CartItem)
        self.product_crud = CrudProduct(session=session, model=Product)

    async def cart_count(self, user: User | None, products: list[ProductRead]) -> int:
        return await self.crud.cart_count(user, products)

    async def add_to_cart(self, user: User, product_id: int, quantity: int) -> dict:
        current_qty = await self.crud.get_cart_quantity(user.id, product_id)
        product = await self.product_crud.get_by_id(product_id)
        total_qty = current_qty + quantity

        if total_qty > product.stock:
            raise HTTPException(400, f"Макс еще: {product.stock - current_qty}")

        await self.crud.add_or_update(user.id, product_id, total_qty)
        return {"cart_qty": total_qty}

    async def get_cart_page(self, current_user, ordered) -> tuple[CartItem, float]:
        cart_items = await self.crud.get_cart_items(current_user.id, ordered)
        total = sum(
            item.product.price * item.quantity for item in cart_items if item.product
        )
        return cart_items, total

    async def remove_cart_item_by_id(self, user_id, item_id) -> None:
        cart_item = await self.crud.get_cart_item_by_id(user_id, item_id)

        if not cart_item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Нет товара в корзине")

        await self.session.delete(cart_item)
        await self.session.commit()

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

        final_qty = min(quantity, product.stock or 0)

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
