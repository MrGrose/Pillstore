from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.db_crud.base import CRUDBase
from app.models.favorites import UserFavorite


class CrudFavorites(CRUDBase):
    def __init__(self, session, model) -> None:
        self.model = model
        self.session = session

    async def get_ids(self, user_id: int) -> set[int]:
        stmt = select(UserFavorite.product_id).where(
            UserFavorite.user_id == user_id
        )
        result = await self.session.scalars(stmt)
        return set(result.all())

    async def add(self, user_id: int, product_id: int) -> UserFavorite:
        existing = await self.get_one(user_id, product_id)
        if existing:
            return existing
        fav = UserFavorite(user_id=user_id, product_id=product_id)
        self.session.add(fav)
        await self.session.commit()
        await self.session.refresh(fav)
        return fav

    async def remove(self, user_id: int, product_id: int) -> bool:
        fav = await self.get_one(user_id, product_id)
        if not fav:
            return False
        await self.session.delete(fav)
        await self.session.commit()
        return True

    async def get_one(
        self, user_id: int, product_id: int
    ) -> UserFavorite | None:
        stmt = select(UserFavorite).where(
            and_(
                UserFavorite.user_id == user_id,
                UserFavorite.product_id == product_id,
            )
        )
        result = await self.session.scalars(stmt)
        return result.first()

    async def get_items_with_products(
        self, user_id: int
    ) -> list[UserFavorite]:
        stmt = (
            select(UserFavorite)
            .options(selectinload(UserFavorite.product))
            .where(UserFavorite.user_id == user_id)
            .order_by(UserFavorite.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        items = list(result.all())
        return [i for i in items if i.product is not None]

    async def merge_ids(
        self, user_id: int, product_ids: list[int]
    ) -> set[int]:
        for pid in product_ids:
            await self.add(user_id, pid)
        return await self.get_ids(user_id)
