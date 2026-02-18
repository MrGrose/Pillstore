from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.users import User as UserModel
from app.schemas.auth import ProfileResponse
from app.services.profile_service import ProfileService

profile_router = APIRouter(prefix="/api/v2", tags=["API v2 Profile"])


@profile_router.get("/profile", response_model=ProfileResponse)
async def api_get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Профиль текущего пользователя и список его заказов."""
    profile_service = ProfileService(db)
    orders = await profile_service.get_orders_profile(current_user)

    return ProfileResponse(
        user=current_user,
        orders=orders,
    )
