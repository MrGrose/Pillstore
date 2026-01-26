from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orders import Order
from app.models.users import User

from app.db_crud.order_crud import CrudOrder


class ProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.order_crud = CrudOrder(session=session, model=Order)

    async def get_orders_profile(self, user: User) -> list[Order]:
        return await self.order_crud.orders_for_profile(user.id)
