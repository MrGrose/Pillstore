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

    def _build_items_data_from_cart(
        self,
        cart_items: list,
        reserved_map: dict[int, int] | None = None,
    ) -> tuple[list[dict], Decimal]:
        items_data = []
        total = Decimal("0")
        for item in cart_items:
            if not item.product or not item.product.is_active:
                continue
            if reserved_map is not None:
                reserved = reserved_map.get(item.product_id, 0)
                available = (item.product.stock or 0) - reserved
                if available < item.quantity:
                    continue
            unit_cost = getattr(item.product, "cost", None) or 0
            items_data.append({
                "product_id": item.product_id,
                "name": item.product.name,
                "quantity": item.quantity,
                "unit_price": float(item.product.price),
                "unit_cost": float(unit_cost),
            })
            total += item.quantity * item.product.price
        return items_data, total

    async def prepare_checkout(
        self, current_user: UserModel, contact_phone: str
    ) -> dict | None:
        cart_items = await self.cart_crud.get_cart_items(current_user.id, ordered=False)
        if not cart_items:
            return None
        product_ids = [item.product_id for item in cart_items]
        reserved_map = await self.order_crud.get_pending_reserved_map(product_ids)
        items_data, total = self._build_items_data_from_cart(cart_items, reserved_map)
        if not items_data:
            return None
        return {
            "items": items_data,
            "total": float(total),
            "contact_phone": contact_phone.strip(),
            "personal_data_consent": True,
        }

    async def get_checkout_order(
        self,
        current_user,
        contact_phone: str | None = None,
        personal_data_consent: bool = False,
    ) -> int:
        cart_items = await self.cart_crud.get_cart_items(current_user.id)
        if not cart_items:
            raise CartNotFoundError(current_user.id)
        items_data, total = self._build_items_data_from_cart(cart_items, reserved_map=None)
        if not items_data:
            raise CartNotFoundError(current_user.id)
        checkout_data = {
            "items": items_data,
            "total": float(total),
            "contact_phone": (contact_phone or "").strip() or None,
            "personal_data_consent": bool(personal_data_consent),
        }
        return await self.create_order_from_checkout(current_user, checkout_data)

    async def create_order_from_checkout(
        self,
        current_user,
        checkout_data: dict,
    ) -> int:
        items_data = checkout_data.get("items") or []
        if not items_data:
            raise CartNotFoundError(current_user.id)

        order = Order(
            user_id=current_user.id,
            status="pending",
            total_amount=Decimal(str(checkout_data.get("total", 0))),
            contact_phone=(checkout_data.get("contact_phone") or "").strip() or None,
            personal_data_consent=bool(checkout_data.get("personal_data_consent")),
        )
        self.session.add(order)
        await self.session.flush()

        for it in items_data:
            product_id = it["product_id"]
            quantity = int(it["quantity"])
            unit_price = Decimal(str(it["unit_price"]))
            unit_cost = Decimal(str(it.get("unit_cost") or 0))
            product = await self.product_crud.get_by_id(product_id)
            if not product or not product.is_active:
                raise BusinessError("Заказ", f"Товар {product_id} недоступен")
            reserved = await self.order_crud.get_pending_reserved(product_id)
            available = (product.stock or 0) - reserved
            if available < quantity:
                raise BusinessError(
                    "Заказ",
                    f"Недостаточно товара на складе: {product.name} "
                    f"(доступно с учётом резерва: {available})",
                )
            total_price = unit_price * quantity
            order_item = OrderItem(
                order_id=order.id,
                product_id=product_id,
                quantity=quantity,
                unit_price=unit_price,
                unit_cost=unit_cost,
                total_price=total_price,
            )
            self.session.add(order_item)
            await self.session.flush()

        await self.session.flush()
        await self.cart_crud.delete_cart_by_user(current_user.id)
        await self.session.commit()
        await self.session.refresh(order)
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

        if order_item.order.status == "paid":
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
        if order.status != "pending":
            raise BusinessError(
                "Заказ",
                "Добавлять позиции можно только в заказ со статусом "
                "«ожидает оплаты»",
            )

        unit_cost = Decimal(str(getattr(product, "cost", 0) or 0))
        await self.order_crud.add_or_update_item(
            order, item_id, quantity, product.price, unit_cost=unit_cost
        )
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
