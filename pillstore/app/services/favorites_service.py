from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud.favorites_crud import CrudFavorites
from app.models.favorites import UserFavorite
from app.models.users import User


class FavoritesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudFavorites(session=session, model=UserFavorite)

    async def get_favorite_ids(self, user: User | None) -> set[int]:
        if not user:
            return set()
        return await self.crud.get_ids(user.id)

    async def toggle(self, user_id: int, product_id: int) -> bool:
        one = await self.crud.get_one(user_id, product_id)
        if one:
            await self.crud.remove(user_id, product_id)
            return False
        await self.crud.add(user_id, product_id)
        return True

    async def add(self, user_id: int, product_id: int) -> bool:
        one = await self.crud.get_one(user_id, product_id)
        if one:
            return True
        await self.crud.add(user_id, product_id)
        return True

    async def remove(self, user_id: int, product_id: int) -> bool:
        return await self.crud.remove(user_id, product_id)

    async def list_for_user(self, user_id: int) -> list[UserFavorite]:
        return await self.crud.get_items_with_products(user_id)

    async def merge_local_ids(self, user_id: int, product_ids: list[int]) -> set[int]:
        return await self.crud.merge_ids(user_id, product_ids)
