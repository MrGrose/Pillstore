from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user_any, get_current_user_optional
from app.exceptions.handlers import (
    BusinessError,
    CartNotFoundError,
    ProductNotFoundError,
)
from app.models.users import User as UserModel
from app.schemas.cart import (
    CartActionResponse,
    CartApi,
    CartCountResponse,
    CartItemApi,
    CartItemCreate,
    CartItemUpdate,
)
from app.services.cart_service import CartService

cart_router = APIRouter(prefix="/api/v2", tags=["API v2 Cart"])


def _cart_to_api(cart_items: list, total: float, user_id: int) -> CartApi:
    """Собрать ответ корзины из списка позиций и общей суммы."""
    return CartApi(
        user_id=user_id,
        items=[
            CartItemApi(id=item.id, quantity=item.quantity, product=item.product)
            for item in cart_items
            if item.product
        ],
        total_quantity=sum(item.quantity for item in cart_items),
        total_price=total,
    )


@cart_router.get("/cart", response_model=CartApi)
async def get_cart(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_any),
):
    """Получить корзину текущего пользователя."""
    cart_service = CartService(db)
    cart_items, total = await cart_service.get_cart_page(current_user, ordered=False)
    return _cart_to_api(cart_items, total, current_user.id)


@cart_router.post("/cart/items", response_model=CartActionResponse)
async def add_item_to_cart(
    item_data: CartItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_any),
):
    """Добавить товар в корзину."""
    cart_service = CartService(db)
    try:
        result = await cart_service.add_to_cart(
            user=current_user,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
        )
        cart_count = await cart_service.get_cart_count(current_user.id)
        return CartActionResponse(
            message="Товар добавлен в корзину",
            cart_count=cart_count,
            cart_qty=result["cart_qty"],
        )
    except ProductNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден",
        )
    except BusinessError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@cart_router.put("/cart/items/{item_id}", response_model=CartActionResponse)
async def update_cart_item(
    item_id: int,
    update_data: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_any),
):
    """Изменить количество товара в корзине."""
    cart_service = CartService(db)
    try:
        cart_item = await cart_service.update_item_quantity(
            current_user.id, item_id, update_data.quantity
        )
        cart_count = await cart_service.get_cart_count(current_user.id)
        return CartActionResponse(
            message="Количество обновлено",
            cart_count=cart_count,
            item={
                "id": cart_item.id,
                "quantity": cart_item.quantity,
                "product_id": cart_item.product_id,
            },
        )
    except CartNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позиция корзины не найдена",
        )
    except (ProductNotFoundError, BusinessError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@cart_router.delete("/cart/items/{item_id}", response_model=CartActionResponse)
async def remove_cart_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_any),
):
    """Удалить позицию из корзины."""
    cart_service = CartService(db)
    try:
        await cart_service.remove_cart_item_by_id(current_user.id, item_id)
        cart_count = await cart_service.get_cart_count(current_user.id)
        return CartActionResponse(
            message="Позиция удалена из корзины",
            cart_count=cart_count,
        )
    except CartNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позиция корзины не найдена",
        )


@cart_router.delete("/cart", response_model=CartActionResponse)
async def clear_cart(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_any),
):
    """Очистить корзину."""
    cart_service = CartService(db)
    await cart_service.clear_cart(current_user.id)
    return CartActionResponse(
        message="Корзина очищена",
        cart_count=0,
    )


@cart_router.get("/cart/count", response_model=CartCountResponse)
async def get_cart_count(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel | None = Depends(get_current_user_optional),
):
    """Количество единиц товаров в корзине (для неавторизованных — 0)."""
    if not current_user:
        return CartCountResponse(count=0)
    cart_service = CartService(db)
    count = await cart_service.get_cart_count(current_user.id)
    return CartCountResponse(count=count)
