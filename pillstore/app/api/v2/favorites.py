from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user_any
from app.models.users import User as UserModel
from app.schemas.favorites import (
    FavoritesIdsResponse,
    MergeFavoritesBody,
    ToggleFavoriteBody,
    ToggleFavoriteResponse,
)
from app.services.favorites_service import FavoritesService

favorites_router = APIRouter(prefix="/api/v2", tags=["API v2 Favorites"])


@favorites_router.post("/favorites/merge", response_model=FavoritesIdsResponse)
async def merge_favorites(
    body: MergeFavoritesBody,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_any),
):
    """Слияние локальных ID с серверным избранным. Вызывать после логина."""
    fav_svc = FavoritesService(db)
    ids = await fav_svc.merge_local_ids(current_user.id, body.product_ids)
    return FavoritesIdsResponse(product_ids=sorted(ids))


@favorites_router.get("/favorites", response_model=FavoritesIdsResponse)
async def get_favorites_ids(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_any),
):
    """Список ID товаров в избранном (для синхронизации клиента)."""
    fav_svc = FavoritesService(db)
    ids = await fav_svc.get_favorite_ids(current_user)
    return FavoritesIdsResponse(product_ids=sorted(ids))


@favorites_router.post("/favorites/toggle", response_model=ToggleFavoriteResponse)
async def toggle_favorite(
    body: ToggleFavoriteBody,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_any),
):
    """Добавить или убрать товар из избранного."""
    fav_svc = FavoritesService(db)
    in_fav = await fav_svc.toggle(current_user.id, body.product_id)
    return ToggleFavoriteResponse(in_favorites=in_fav)
