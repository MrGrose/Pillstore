from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_seller
from app.exceptions.handlers import (
    BusinessError,
    OrderNotFoundError,
    ProductNotFoundError,
    UserNotFoundError,
)
from app.models.users import User as UserModel
from app.schemas.auth import MessageResponse, UserCreate, UserResponse
from app.schemas.product import (
    AdminProductsPaginatedResponse,
    ProductCreate,
    ProductSchema,
    ProductUpdate,
    product_to_schema,
)
from app.schemas.order import OrderSchema
from app.services.admin_service import AdminService
from app.services.user_service import UserService

admin_router = APIRouter(prefix="/api/v2", tags=["API v2 Admin"])


@admin_router.get("/admin/stats", response_model=dict)
async def api_admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Статистика дашборда (только для продавца)."""
    admin_service = AdminService(db)
    return await admin_service.get_stats()


@admin_router.get("/admin/users", response_model=list[UserResponse])
async def api_admin_get_users(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Список пользователей (только для продавца)."""
    user_service = UserService(db)
    return await user_service.get_all_users()


@admin_router.post("/admin/users", response_model=UserResponse)
async def api_admin_create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Создать пользователя (только для продавца)."""
    user_service = UserService(db)
    try:
        await user_service.create_admin_user(
            email=user_data.email,
            password=user_data.password,
            role=user_data.role,
        )
        return await user_service.get_user_by_email(user_data.email)
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@admin_router.put("/admin/users/{user_id}", response_model=UserResponse)
async def api_admin_update_user(
    user_id: int,
    email: str = Form(...),
    password: Optional[str] = Form(None),
    role: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Обновить пользователя (только для продавца)."""
    user_service = UserService(db)
    try:
        await user_service.update_admin_user(
            user_id=user_id,
            email=email,
            password=password,
            role=role,
        )
        return await user_service.get_user_by_id(user_id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@admin_router.delete("/admin/users/{user_id}", response_model=MessageResponse)
async def api_admin_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Удалить пользователя (только для продавца)."""
    user_service = UserService(db)
    try:
        msg = await user_service.delete_admin_user(user_id)
        return MessageResponse(message=msg)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@admin_router.get("/admin/orders", response_model=list[OrderSchema])
async def api_admin_get_orders(
    status_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Список заказов с опциональным фильтром по статусу (только для продавца)."""
    admin_service = AdminService(db)
    return await admin_service.get_orders_for_admin(status_filter)


@admin_router.put("/admin/orders/{order_id}/status", response_model=MessageResponse)
async def api_admin_update_order_status(
    order_id: int,
    status: str = Query(..., pattern="^(pending|paid|transit|delivered|cancelled)$"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Обновить статус заказа (только для продавца)."""
    admin_service = AdminService(db)
    try:
        await admin_service.order_status_admin(order_id, status)
        return MessageResponse(message=f"Order {order_id} status updated to {status}")
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )


@admin_router.delete("/admin/orders/{order_id}", response_model=MessageResponse)
async def api_admin_delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Удалить заказ и вернуть товары на склад (только для продавца)."""
    admin_service = AdminService(db)
    try:
        await admin_service.remove_order_admin(order_id)
        return MessageResponse(message=f"Order {order_id} deleted")
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )


@admin_router.get("/admin/products", response_model=AdminProductsPaginatedResponse)
async def api_admin_get_products(
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Товаров на странице"),
    active_only: bool = Query(True, description="True — активные, False — неактивные"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Список товаров по страницам (по умолчанию 20 шт)."""
    admin_service = AdminService(db)
    raw = await admin_service.get_products_for_admin_paginated(
        active_only=active_only, page=page, page_size=page_size
    )
    return AdminProductsPaginatedResponse(
        items=[product_to_schema(p) for p in raw["items"]],
        total=raw["total"],
        page=raw["page"],
        page_size=raw["page_size"],
        total_active=raw["total_active"],
        total_inactive=raw["total_inactive"],
    )


@admin_router.post("/admin/products", response_model=ProductSchema)
async def api_admin_create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Создать товар (только для продавца). URL должен быть уникален."""
    admin_service = AdminService(db)
    data = product.model_copy(update={"seller_id": current_user.id})
    try:
        created = await admin_service.create_product_check_url(data, None)
        return created
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@admin_router.put("/admin/products/{product_id}", response_model=ProductSchema)
async def api_admin_update_product(
    product_id: int,
    product: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Обновить товар (только для продавца)."""
    admin_service = AdminService(db)
    try:
        await admin_service.update_product_admin(
            product_id=product_id,
            data=product,
            category_ids=product.category_ids or [],
            image=None,
        )
        updated = await admin_service.get_product_by_id(product_id)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        return updated
    except ProductNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@admin_router.delete("/admin/products/{product_id}", response_model=MessageResponse)
async def api_admin_delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Удалить товар (только для продавца)."""
    admin_service = AdminService(db)
    try:
        msg = await admin_service.remove_product_admin(product_id)
        return MessageResponse(message=msg)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
