from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import templates
from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.users import User
from app.services.cart import get_cart_count
from app.services.cart_service import CartService
from app.services.favorites_service import FavoritesService
from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("/", response_class=HTMLResponse, name="profile_page")
async def profile_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cart_count: int = Depends(get_cart_count),
):
    profile_svc = ProfileService(db)
    orders = await profile_svc.get_orders_profile(current_user)
    fav_svc = FavoritesService(db)
    favorites_count = len(await fav_svc.get_favorite_ids(current_user))

    return templates.TemplateResponse(
        "/profile/profile.html",
        {
            "current_user": current_user,
            "orders": orders,
            "request": request,
            "cart_count": cart_count,
            "favorites_count": favorites_count,
        },
    )


@router.get("/favorites", response_class=HTMLResponse, name="profile_favorites")
async def profile_favorites_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cart_count: int = Depends(get_cart_count),
):
    fav_svc = FavoritesService(db)
    items = await fav_svc.list_for_user(current_user.id)
    cart_svc = CartService(db)
    cart_items = await cart_svc.crud.get_cart_items(current_user.id, False)
    cart_qty_by_product = {item.product_id: item.quantity for item in cart_items}
    for fav in items:
        fav.product.cart_qty = cart_qty_by_product.get(fav.product.id, 0)

    return templates.TemplateResponse(
        "/profile/favorites.html",
        {
            "request": request,
            "current_user": current_user,
            "cart_count": cart_count,
            "favorites_items": items,
        },
    )


@router.post("/favorites/remove/{product_id}", response_class=RedirectResponse)
async def profile_favorites_remove(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fav_svc = FavoritesService(db)
    await fav_svc.remove(current_user.id, product_id)
    return RedirectResponse(url="/profile/favorites", status_code=303)


@router.post("/favorites/toggle")
async def profile_favorites_toggle(
    product_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fav_svc = FavoritesService(db)
    in_favorites = await fav_svc.toggle(current_user.id, product_id)
    return {"in_favorites": in_favorites}
