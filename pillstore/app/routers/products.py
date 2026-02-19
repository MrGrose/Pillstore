from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import templates
from app.core.deps import get_db
from app.core.security import get_current_user_optional
from app.models.users import User
from app.services.cart_service import CartService
from app.services.favorites_service import FavoritesService
from app.services.product_service import ProductService


router = APIRouter(prefix="/products")


@router.get("", response_class=HTMLResponse)
async def products_page(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search_product: str | None = Query(None),
    category_id: int = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    product_svc = ProductService(db)
    cart_svc = CartService(db)
    pagination = await product_svc.get_products_page(
        page, page_size, search_product, request, category_id
    )
    cart_count = await cart_svc.cart_count(current_user, pagination.items)
    flat_tree = await product_svc.get_flat_tree()
    fav_svc = FavoritesService(db)
    favorite_ids = list(await fav_svc.get_favorite_ids(current_user))

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "cart_count": cart_count,
            "current_user": current_user,
            "pagination": pagination,
            "search": search_product,
            "flat_tree": flat_tree,
            "active_category_id": category_id,
            "favorite_ids": favorite_ids,
        },
    )


@router.get("/{product_id}", response_class=HTMLResponse, name="product_detail")
async def product_detail(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    product_svc = ProductService(db)
    cart_svc = CartService(db)
    product = await product_svc.get_product_detail(product_id, current_user)
    cart_count = await cart_svc.cart_count(current_user, [])
    fav_svc = FavoritesService(db)
    favorite_ids = list(await fav_svc.get_favorite_ids(current_user))

    return templates.TemplateResponse(
        "product_detail.html",
        {
            "request": request,
            "product": product,
            "current_user": current_user,
            "cart_count": cart_count,
            "favorite_ids": favorite_ids,
        },
    )


@router.get("/api/stock/{product_id}")
async def get_stock(product_id: int, db: AsyncSession = Depends(get_db)):
    product_svc = ProductService(db).crud
    product_stock = await product_svc.get_by_id(product_id)
    return {"stock": product_stock or 0}
