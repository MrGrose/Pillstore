from sqlalchemy import func, select

from app.db_crud.base import CRUDBase

from app.models.orders import Order
from app.models.products import Product


class CrudAdmin(CRUDBase):
    def __init__(self, session) -> None:
        self.session = session

    async def dashboard_stats(self) -> dict:
        stats = {
            "total_orders": await self.session.scalar(
                select(func.count()).select_from(Order)
            ),
            "total_revenue": await self.session.scalar(
                select(func.sum(Order.total_amount)).select_from(Order)
            )
            or 0,
            "total_products": await self.session.scalar(
                select(func.count()).select_from(Product)
            ),
            "pending_orders": await self.session.scalar(
                select(func.count()).select_from(Order).where(Order.status == "pending")
            ),
        }
        return stats
