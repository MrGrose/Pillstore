from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db_crud.base import CRUDBase
from app.models.orders import Order, OrderItem


class CrudOrder(CRUDBase):
    def __init__(self, session, model) -> None:
        self.model = model
        self.session = session

    async def get_order_with_items(self, id: int):
        stmt = (
            select(self.model)
            .options(
                selectinload(self.model.user),
                selectinload(self.model.items).selectinload(OrderItem.product),
            )
            .where(self.model.id == id)
        )
        db_result = await self.session.scalars(stmt)
        return db_result.first()

    async def recalculate_total(self, order: Order) -> None:
        db_result = select(func.sum(OrderItem.quantity * OrderItem.unit_price)).where(
            OrderItem.order_id == order.id
        )
        result = await self.session.execute(db_result)
        total = result.scalar() or Decimal("0")
        order.total_amount = total

    async def get_order_item_detailed(self, order_id: int, item_id: int):
        return await self.session.scalar(
            select(OrderItem)
            .options(selectinload(OrderItem.product), selectinload(OrderItem.order))
            .where(OrderItem.id == item_id, OrderItem.order_id == order_id)
        )

    async def return_item(self, order_item: OrderItem):
        order_item.product.stock += order_item.quantity
        await self.session.delete(order_item)
        await self.session.flush()

    async def delete_empty_order(self, order: Order):
        await self.session.delete(order)
        await self.session.commit()

    async def get_order_items_count(self, order_id: int) -> int:
        return await self.session.scalar(
            select(func.count(OrderItem.id)).where(OrderItem.order_id == order_id)
        )

    async def get_order_detailed(self, order_id: int, user_id: int):
        return await self.session.scalar(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id, Order.user_id == user_id)
        )

    async def add_or_update_item(
        self, order: Order, product_id: int, quantity: int, product_price: Decimal
    ):
        existing_item = next(
            (item for item in order.items if item.product_id == product_id), None
        )

        if existing_item:
            existing_item.quantity += quantity
            existing_item.unit_price = product_price
            existing_item.total_price = existing_item.quantity * product_price
        else:
            item = OrderItem(
                order_id=order.id,
                product_id=product_id,
                quantity=quantity,
                unit_price=product_price,
                total_price=quantity * product_price,
            )
            self.session.add(item)
