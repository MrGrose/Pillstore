from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.db_crud.base import CRUDBase
from app.models.associations import product_categories
from app.models.batches import ProductBatch
from app.models.orders import Order, OrderItem
from app.models.products import Product


SALES_STATUSES = ("paid", "transit", "delivered")


def _period_to_dates(period: str):
    today = date.today()
    if period == "1d":
        start = today
    elif period == "7d":
        start = today - timedelta(days=7)
    elif period == "30d":
        start = today - timedelta(days=30)
    elif period == "6m":
        start = today - timedelta(days=182)
    elif period == "1y":
        start = today - timedelta(days=365)
    else:
        start = today - timedelta(days=30)
    return start, today


class CrudAdmin(CRUDBase):
    def __init__(self, session) -> None:
        self.session = session

    async def dashboard_stats(self) -> dict:
        total_revenue = await self.session.scalar(
            select(func.coalesce(func.sum(Order.total_amount), 0)).select_from(Order)
        )
        total_revenue = Decimal(str(total_revenue or 0))

        cost_expr = func.sum(
            OrderItem.quantity * func.coalesce(OrderItem.unit_cost, 0)
        )
        total_cost = await self.session.scalar(
            select(func.coalesce(cost_expr, 0)).select_from(OrderItem)
        )
        total_cost = Decimal(str(total_cost or 0))
        total_margin = total_revenue - total_cost

        total_orders = await self.session.scalar(
            select(func.count()).select_from(Order)
        )
        total_products = await self.session.scalar(
            select(func.count()).select_from(Product)
        )
        pending_orders = await self.session.scalar(
            select(func.count()).select_from(Order).where(
                Order.status == "pending"
            )
        )
        return {
            "total_orders": total_orders or 0,
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_margin": total_margin,
            "total_products": total_products or 0,
            "pending_orders": pending_orders or 0,
        }

    async def sales_report(
        self, date_from: date, date_to: date
    ) -> list[dict]:
        stmt = (
            select(
                Product.name,
                func.sum(OrderItem.quantity).label("qty"),
                func.sum(OrderItem.total_price).label("revenue"),
                func.sum(
                    OrderItem.quantity * func.coalesce(OrderItem.unit_cost, 0)
                ).label("cost"),
            )
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .where(Order.status.in_(SALES_STATUSES))
            .where(func.date(Order.created_at) >= date_from)
            .where(func.date(Order.created_at) <= date_to)
            .group_by(Product.id, Product.name)
            .order_by(func.sum(OrderItem.quantity).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        result = []
        for r in rows:
            cost = float(r.cost or 0)
            revenue = float(r.revenue or 0)
            result.append({
                "product_name": r.name,
                "quantity": int(r.qty or 0),
                "revenue": round(revenue, 2),
                "margin": round(revenue - cost, 2),
            })
        return result

    async def sales_by_category(
        self, date_from: date, date_to: date
    ) -> list[dict]:
        from app.models.categories import Category
        one_cat = (
            select(
                product_categories.c.product_id,
                func.min(product_categories.c.category_id).label("category_id"),
            )
            .group_by(product_categories.c.product_id)
        ).subquery()
        stmt = (
            select(
                Category.name,
                func.sum(OrderItem.quantity).label("qty"),
                func.sum(OrderItem.total_price).label("revenue"),
            )
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .join(one_cat, one_cat.c.product_id == Product.id)
            .join(Category, Category.id == one_cat.c.category_id)
            .where(Order.status.in_(SALES_STATUSES))
            .where(func.date(Order.created_at) >= date_from)
            .where(func.date(Order.created_at) <= date_to)
            .group_by(Category.id, Category.name)
            .order_by(func.sum(OrderItem.total_price).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {"name": r.name, "quantity": int(r.qty or 0), "revenue": float(r.revenue or 0)}
            for r in rows
        ]

    async def sales_by_brand(
        self, date_from: date, date_to: date
    ) -> list[dict]:
        stmt = (
            select(
                Product.brand,
                func.sum(OrderItem.quantity).label("qty"),
                func.sum(OrderItem.total_price).label("revenue"),
            )
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .where(Order.status.in_(SALES_STATUSES))
            .where(func.date(Order.created_at) >= date_from)
            .where(func.date(Order.created_at) <= date_to)
            .group_by(Product.brand)
            .order_by(func.sum(OrderItem.total_price).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {"name": r.brand or "—", "quantity": int(r.qty or 0), "revenue": float(r.revenue or 0)}
            for r in rows
        ]

    async def top_products(
        self, date_from: date, date_to: date, limit: int = 5
    ) -> list[dict]:
        report = await self.sales_report(date_from, date_to)
        return report[:limit]

    async def top_categories(
        self, date_from: date, date_to: date, limit: int = 5
    ) -> list[dict]:
        rows = await self.sales_by_category(date_from, date_to)
        return rows[:limit]

    async def batches_expiring_soon(self, days: int = 30) -> list[dict]:
        from datetime import date as date_type
        today = date_type.today()
        end = today + timedelta(days=days)
        stmt = (
            select(ProductBatch, Product.name)
            .join(Product, Product.id == ProductBatch.product_id)
            .where(ProductBatch.quantity > 0)
            .where(ProductBatch.expiry_date.isnot(None))
            .where(ProductBatch.expiry_date >= today)
            .where(ProductBatch.expiry_date <= end)
            .order_by(ProductBatch.expiry_date.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "product_name": name,
                "batch_id": b.id,
                "expiry_date": b.expiry_date,
                "quantity": b.quantity,
            }
            for b, name in rows
        ]

    async def trend_by_day(
        self, date_from: date, date_to: date
    ) -> list[dict]:
        stmt = (
            select(
                func.date(Order.created_at).label("day"),
                func.sum(Order.total_amount).label("revenue"),
                func.count(Order.id).label("order_count"),
            )
            .select_from(Order)
            .where(Order.status.in_(SALES_STATUSES))
            .where(func.date(Order.created_at) >= date_from)
            .where(func.date(Order.created_at) <= date_to)
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at))
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "date": str(r.day),
                "revenue": float(r.revenue or 0),
                "order_count": int(r.order_count or 0),
            }
            for r in rows
        ]
