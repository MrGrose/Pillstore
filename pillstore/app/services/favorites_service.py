from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud.cart_crud import CrudCart
from app.db_crud.favorites_crud import CrudFavorites
from app.models.cart_items import CartItem
from app.models.favorites import UserFavorite
from app.models.users import User


class FavoritesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudFavorites(session=session, model=UserFavorite)
        self.cart_crud = CrudCart(session=session, model=CartItem)

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

    async def list_for_user_with_cart_quantities(
        self, user_id: int
    ) -> list[UserFavorite]:
        items = await self.crud.get_items_with_products(user_id)
        cart_items = await self.cart_crud.get_cart_items(user_id, ordered=False)
        cart_qty_by_product = {item.product_id: item.quantity for item in cart_items}
        for fav in items:
            fav.product.cart_qty = cart_qty_by_product.get(fav.product.id, 0)
        return items

    async def merge_local_ids(self, user_id: int, product_ids: list[int]) -> set[int]:
        return await self.crud.merge_ids(user_id, product_ids)
