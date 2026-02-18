from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.cart_items import CartItem as CartItemModel
from app.models.users import User as UserModel


async def get_cart_count(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> int:
    result = await db.scalar(
        select(func.coalesce(func.sum(CartItemModel.quantity), 0)).where(
            CartItemModel.user_id == current_user.id
        )
    )
    return result or 0
