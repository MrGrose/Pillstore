from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud.batch_crud import CrudBatch
from app.db_crud.cart_crud import CrudCart
from app.db_crud.order_crud import CrudOrder
from app.db_crud.products_crud import CrudProduct

from app.models.cart_items import CartItem
from app.models.orders import Order, OrderItem
from app.models.users import User as UserModel
from app.models.products import Product
from app.exceptions.handlers import (
    ProductNotFoundError,
    OrderNotFoundError,
    CartNotFoundError,
    BusinessError,
)


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cart_crud = CrudCart(session=session, model=CartItem)
        self.order_crud = CrudOrder(session=session, model=Order)
        self.product_crud = CrudProduct(session=session, model=Product)
        self.batch_crud = CrudBatch(session)

    async def get_checkout_order(self, current_user) -> int:
        cart_items = await self.cart_crud.get_cart_items(current_user.id)
        if not cart_items:

            raise CartNotFoundError(current_user.id)

        order = Order(user_id=current_user.id, status="pending")
        total_amount = Decimal("0")

        for cart_item in cart_items:
            product = cart_item.product
            if not product or not product.is_active:
                raise BusinessError(
                    "Заказ", f"Продукт {cart_item.product_id} не доступен"
                )
            if product.stock < cart_item.quantity:
                raise BusinessError(
                    "Заказ", f"Недостаточно товара на складе {product.name}"
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
            raise OrderNotFoundError(order_id)
        if order.user_id != user_id:
            raise BusinessError("Заказ", "Нет доступа к чужому заказу")
        if order.status != "pending":
            raise BusinessError("Заказ", "Заказ уже подтвержден")

        for item in order.items:
            product = await self.product_crud.get_by_id(item.product_id)
            if not product:
                raise BusinessError("Заказ", f"Товар {item.product_id} не найден")
            total = (
                await self.batch_crud.get_total_stock_from_batches(product.id)
                if product.id
                else 0
            )
            if total == 0:
                total = product.stock or 0
            if total < item.quantity:
                raise BusinessError(
                    "Заказ", f"Товара {product.name} больше нет"
                )
            try:
                await self.batch_crud.deduct_fifo(
                    product.id,
                    item.quantity,
                    order.id,
                    item.id,
                )
            except ValueError as e:
                raise BusinessError("Заказ", str(e)) from e

        order.status = "paid"
        await self.session.commit()
        return order

    async def get_order_for_payment(self, order_id: int, user_id: int) -> Order:
        order = await self.order_crud.get_order_with_items(order_id)
        if not order:
            raise OrderNotFoundError(order_id)
        if order.user_id != user_id:
            raise OrderNotFoundError(order_id)

        return order

    async def get_order_with_items(self, order_id: int) -> Order | None:
        return await self.order_crud.get_order_with_items(order_id)

    async def get_order_for_user(
        self, order_id: int, current_user: UserModel
    ) -> tuple[Order, bool]:
        order = await self.order_crud.get_order_with_items(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        is_admin = current_user.role == "seller"
        if not is_admin and order.user_id != current_user.id:
            raise BusinessError("Заказ", "Нет доступа к чужому заказу")

        return order, is_admin

    async def return_item_to_stock(
        self, order_id: int, item_id: int, current_user: UserModel
    ) -> str:
        order_item = await self.order_crud.get_order_item_detailed(order_id, item_id)
        if not order_item:
            raise BusinessError("Позиция", f"Позиция {item_id} не найдена")

        if (
            order_item.order.user_id != current_user.id
            and current_user.role != "seller"
        ):
            raise BusinessError("Заказ", "Нет доступа")

        await self.batch_crud.return_deductions_for_order_item(order_item)
        await self.session.delete(order_item)
        await self.session.flush()
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
            raise OrderNotFoundError(order_id)

        product = await self.product_crud.get_product_available(item_id, quantity)
        if not product:
            raise ProductNotFoundError(item_id)

        if order.user_id != current_user.id and current_user.role != "seller":
            raise BusinessError("Заказ", "Нет доступа")

        await self.order_crud.add_or_update_item(
            order, item_id, quantity, product.price
        )
        await self.session.flush()
        order_item = await self.order_crud.get_order_item_by_product(
            order.id, item_id
        )
        if order_item:
            try:
                await self.batch_crud.deduct_fifo(
                    item_id,
                    quantity,
                    order.id,
                    order_item.id,
                )
            except ValueError as e:
                raise BusinessError("Заказ", str(e)) from e

        await self.session.flush()
        await self.order_crud.recalculate_total(order)
        await self.session.commit()

        return f"orders/{order_id}?message={product.name} ({quantity} шт.) добавлен"

    async def get_orders_list(
        self,
        current_user: UserModel,
        page: int = 1,
        page_size: int = 10,
        status_filter: str | None = None,
        all_orders: bool = False,
    ) -> tuple[list[Order], int]:
        user_id = (
            None if all_orders and current_user.role == "seller" else current_user.id
        )
        orders, total = await self.order_crud.get_orders_paginated(
            user_id=user_id,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
        return orders, total

    async def cancel_order(self, order_id: int, current_user: UserModel) -> Order:
        order = await self.order_crud.get_order_with_items(order_id)
        if not order:
            raise OrderNotFoundError(order_id)

        if order.user_id != current_user.id:
            raise BusinessError("Заказ", "Нет доступа к чужому заказу")

        if order.status != "pending":
            raise BusinessError(
                "Заказ", f"Нельзя отменить заказ со статусом '{order.status}'"
            )

        order.status = "cancelled"
        await self.session.commit()
        await self.session.refresh(order)
        return order
