from decimal import Decimal
from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from app.db_crud.base import CRUDBase
from app.models.orders import Order, OrderItem
from app.models.users import User


class CrudOrder(CRUDBase):
    def __init__(self, session, model) -> None:
        self.model = model
        self.session = session

    async def get_order_with_items(self, id: int) -> Order:
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

    async def return_item(self, order_item: OrderItem) -> None:
        order_item.product.stock += order_item.quantity
        await self.session.delete(order_item)
        await self.session.flush()

    async def delete_empty_order(self, order: Order) -> None:
        await self.session.delete(order)
        await self.session.commit()

    async def get_order_items_count(self, order_id: int) -> int:
        return await self.session.scalar(
            select(func.count(OrderItem.id)).where(OrderItem.order_id == order_id)
        )

    async def add_or_update_item(
        self, order: Order, product_id: int, quantity: int, product_price: Decimal
    ) -> None:
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

    async def orders_for_profile(self, user: int) -> list[Order]:
        db_orders = await self.session.scalars(
            select(self.model).where(self.model.user_id == user)
        )
        orders = list(db_orders.all())
        return orders

    async def get_user_order_counts(self, user: User) -> int:
        result = await self.session.scalar(
            select(func.count(self.model.id)).where(self.model.user_id == user.id)
        )
        return result

    async def get_orders_list(self, status_filter: str | None) -> list[Order]:
        query = (
            select(self.model)
            .options(selectinload(self.model.user))
            .order_by(self.model.created_at.desc())
        )
        if status_filter and status_filter != "all":
            query = query.where(self.model.status == status_filter)
        result = await self.session.scalars(query)
        return list(result.all())

    async def get_order(
        self, order_id: int, user_id: int = None, load_products: bool = False
    ) -> Order:
        stmt = select(self.model).options(selectinload(self.model.items))
        if load_products:
            stmt = stmt.options(
                selectinload(self.model.items).selectinload(OrderItem.product)
            )
        if user_id:
            stmt = stmt.where(self.model.id == order_id, self.model.user_id == user_id)
        else:
            stmt = stmt.where(self.model.id == order_id)
        stmt = stmt.options(selectinload(self.model.user))

        return await self.session.scalar(stmt)
