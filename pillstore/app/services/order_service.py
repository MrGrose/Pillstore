from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud.cart_crud import CrudCart
from app.db_crud.products_crud import CrudProduct
from app.db_crud.order_crud import CrudOrder

from app.models.cart_items import CartItem
from app.models.orders import Order, OrderItem
from app.models.users import User as UserModel
from app.models.products import Product


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cart_crud = CrudCart(session=session, model=CartItem)
        self.order_crud = CrudOrder(session=session, model=Order)
        self.product_crud = CrudProduct(session=session, model=Product)

    async def get_checkout_order(self, current_user) -> int:
        cart_items = await self.cart_crud.get_cart_items(current_user.id)
        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пустая корзина",
            )

        order = Order(user_id=current_user.id, status="pending")
        total_amount = Decimal("0")

        for cart_item in cart_items:
            product = cart_item.product
            if not product or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Продукт {cart_item.product_id} не доступен",
                )
            if product.stock < cart_item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Недостаточно товара на складе {product.name}",
                )

            order_item = OrderItem(
                product_id=cart_item.product_id,
                quantity=cart_item.quantity,
                unit_price=product.price,
                total_price=product.price * cart_item.quantity,
            )
            order.items.append(order_item)
            total_amount += cart_item.quantity * product.price

        order.total_amount = total_amount
        self.session.add(order)
        await self.cart_crud.delete_cart_by_user(current_user.id)
        await self.session.commit()

        return order.id

    async def confirm_payment(self, order_id: int, user_id: int) -> Order:
        order = await self.order_crud.get_order_with_items(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
            )
        if order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа"
            )
        if order.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Заказ уже подтвержден"
            )

        for item in order.items:
            product = await self.product_crud.get_by_id(item.product_id)
            if product.stock < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Товара {product.name} больше нет",
                )
            product.stock -= item.quantity

        order.status = "pending"
        await self.session.commit()
        return order

    async def get_order_for_payment(self, order_id: int, user_id: int) -> Order:
        order = await self.order_crud.get_order_with_items(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заказ не найден",
            )
        if order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заказ не найден",
            )

        return order

    async def get_order_for_user(
        self, order_id: int, current_user: UserModel
    ) -> tuple[Order, bool]:
        order = await self.order_crud.get_order_with_items(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заказ не найден",
            )

        is_admin = current_user.role == "seller"
        if not is_admin and order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к чужому заказу",
            )

        return order, is_admin

    async def return_item_to_stock(
        self, order_id: int, item_id: int, current_user: UserModel
    ) -> str:
        order_item = await self.order_crud.get_order_item_detailed(order_id, item_id)
        if not order_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Позиция не найдена",
            )

        if (
            order_item.order.user_id != current_user.id
            and current_user.role != "seller"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав",
            )

        await self.order_crud.return_item(order_item)
        await self.order_crud.recalculate_total(order_item.order)
        await self.session.commit()

        if await self.order_crud.get_order_items_count(order_id) == 0:
            await self.order_crud.delete_empty_order(order_item.order)
            return "admin?tab=orders&message=Заказ отменён"

        return f"orders/{order_id}?message=Товар возвращён"

    async def add_item_to_order(
        self, order_id: int, item_id: int, quantity: int, current_user: UserModel
    ) -> str:
        order = await self.order_crud.get_order(order_id, current_user.id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заказ не найден",
            )

        product = await self.product_crud.get_product_available(item_id, quantity)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Товар недоступен",
            )

        if order.user_id != current_user.id and current_user.role != "seller":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав",
            )

        await self.order_crud.add_or_update_item(
            order, item_id, quantity, product.price
        )
        product.stock -= quantity

        await self.session.flush()
        await self.order_crud.recalculate_total(order)
        await self.session.commit()

        return f"orders/{order_id}?message={product.name} ({quantity} шт.) добавлен"
