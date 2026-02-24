from decimal import Decimal

from app.db_crud.base import CRUDBase
from app.models.orders import Order, OrderItem
from app.models.users import User
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload


class CrudOrder(CRUDBase):
    def __init__(self, session, model) -> None:
        self.model = model
        self.session = session

    async def get_order_with_items(self, id: int) -> Order | None:
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

    async def get_order_item_detailed(self, order_id: int, item_id: int) -> OrderItem | None:
        return await self.session.scalar(
            select(OrderItem)
            .options(selectinload(OrderItem.product), selectinload(OrderItem.order))
            .where(OrderItem.id == item_id, OrderItem.order_id == order_id)
        )

    async def get_order_item_by_product(
        self, order_id: int, product_id: int
    ) -> OrderItem | None:
        return await self.session.scalar(
            select(OrderItem).where(
                OrderItem.order_id == order_id,
                OrderItem.product_id == product_id,
            )
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
        self,
        order: Order,
        product_id: int,
        quantity: int,
        product_price: Decimal,
        unit_cost: Decimal | None = None,
    ) -> None:
        existing_item = next(
            (item for item in order.items if item.product_id == product_id), None
        )

        if existing_item:
            existing_item.quantity += quantity
            existing_item.unit_price = product_price
            existing_item.total_price = existing_item.quantity * product_price
            if unit_cost is not None:
                existing_item.unit_cost = unit_cost
        else:
            item = OrderItem(
                order_id=order.id,
                product_id=product_id,
                quantity=quantity,
                unit_price=product_price,
                unit_cost=unit_cost,
                total_price=quantity * product_price,
            )
            self.session.add(item)

    async def orders_for_profile(self, user: int) -> list[Order]:
        db_orders = await self.session.scalars(
            select(self.model)
            .where(self.model.user_id == user)
            .order_by(self.model.created_at.desc())
        )
        orders = list(db_orders.all())
        return orders

    async def get_user_order_counts(self, user: User) -> int:
        result = await self.session.scalar(
            select(func.count(self.model.id)).where(self.model.user_id == user.id)
        )
        return result

    async def get_orders_user_list(
        self,
        status_filter: str | None = None,
        load_items: bool = False,
    ) -> list[Order]:
        query = (
            select(self.model)
            .options(selectinload(self.model.user))
            .order_by(self.model.created_at.desc())
        )
        if load_items:
            query = query.options(
                selectinload(self.model.items).selectinload(OrderItem.product)
            )
        if status_filter and status_filter != "all":
            query = query.where(self.model.status == status_filter)
        result = await self.session.scalars(query)
        return list(result.all())

    async def get_orders_containing_product(
        self, product_id: int, status_filter: str = "pending"
    ) -> list[Order]:
        subq = (
            select(OrderItem.order_id)
            .where(OrderItem.product_id == product_id)
            .distinct()
        )
        stmt = (
            select(self.model)
            .options(selectinload(self.model.user))
            .where(
                self.model.id.in_(subq),
                self.model.status == status_filter,
            )
            .order_by(self.model.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_order(
        self, order_id: int, user_id: int | None = None, load_products: bool = False
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

    async def get_pending_reserved(self, product_id: int) -> int:
        stmt = (
            select(func.coalesce(func.sum(OrderItem.quantity), 0))
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                OrderItem.product_id == product_id,
                Order.status == "pending",
            )
        )
        result = await self.session.scalar(stmt)
        return int(result or 0)

    async def get_pending_reserved_map(
        self, product_ids: list[int]
    ) -> dict[int, int]:
        if not product_ids:
            return {}
        stmt = (
            select(OrderItem.product_id, func.sum(OrderItem.quantity))
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.status == "pending",
                OrderItem.product_id.in_(product_ids),
            )
            .group_by(OrderItem.product_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {int(pid): int(qty) for pid, qty in rows}

    async def get_orders_paginated(
        self,
        user_id: int | None = None,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Order], int]:
        conditions = []
        if user_id is not None:
            conditions.append(self.model.user_id == user_id)
        if status_filter and status_filter != "all":
            conditions.append(self.model.status == status_filter)

        count_stmt = select(func.count()).select_from(self.model)
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total = int((await self.session.execute(count_stmt)).scalar() or 0)

        stmt = (
            select(self.model)
            .options(
                selectinload(self.model.user),
                selectinload(self.model.items).selectinload(OrderItem.product),
            )
            .order_by(self.model.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if conditions:
            stmt = stmt.where(*conditions)

        orders = list((await self.session.scalars(stmt)).all())
        return orders, total
