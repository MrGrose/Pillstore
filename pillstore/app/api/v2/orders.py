from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.exceptions.handlers import (
    BusinessError,
    CartNotFoundError,
    OrderNotFoundError,
)
from app.models.users import User as UserModel
from app.schemas.order import OrderList, OrderSchema
from app.services.order_service import OrderService

orders_router = APIRouter(prefix="/api/v2", tags=["API v2 Orders"])


class OrderCheckoutResponse(BaseModel):
    """Ответ эндпоинта оформления заказа (заказ, созданный из корзины)."""

    order: OrderSchema = Field(..., description="Созданный заказ")
    order_url: str = Field(..., description="URL для получения заказа")
    payment_url: str = Field(..., description="URL для получения информации об оплате")


class OrderItemAddRequest(BaseModel):
    """Тело запроса для добавления позиции в существующий заказ."""

    product_id: int = Field(..., ge=1, description="ID товара")
    quantity: int = Field(1, ge=1, le=99, description="Количество")


class OrderActionResponse(BaseModel):
    """Общий ответ для эндпоинтов изменения заказа."""

    message: str = Field(..., description="Результат операции")
    order: OrderSchema | None = Field(None, description="Обновлённый заказ (если есть)")
    order_deleted: bool = Field(
        False, description="Истина, если заказ удалён (после возврата всех позиций)"
    )


@orders_router.get("/orders", response_model=OrderList)
async def api_get_user_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    status_filter: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    all_orders: bool = Query(
        False, description="Только для seller: показать заказы всех пользователей"
    ),
):
    """Список заказов с пагинацией. По умолчанию — свои; продавец может запросить все (all_orders=true)."""
    order_service = OrderService(db)

    if all_orders and current_user.role != "seller":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для просмотра всех заказов",
        )

    orders, total = await order_service.get_orders_list(
        current_user=current_user,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        all_orders=all_orders,
    )

    return OrderList(items=orders, total=total, page=page, page_size=page_size)


@orders_router.post(
    "/orders/checkout",
    response_model=OrderCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def api_checkout_order(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Создать заказ из корзины (оформление заказа)."""
    order_service = OrderService(db)

    try:
        order_id = await order_service.get_checkout_order(current_user)
    except CartNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Корзина пуста",
        )

    created_order = await order_service.get_order_with_items(order_id)
    if not created_order:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать заказ",
        )

    return OrderCheckoutResponse(
        order=created_order,
        order_url=f"/api/v2/orders/{order_id}",
        payment_url=f"/api/v2/orders/payment/{order_id}",
    )


@orders_router.put("/orders/{order_id}/cancel", response_model=OrderSchema)
async def api_cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Отменить заказ. Только в статусе «ожидает оплаты», только владелец."""
    order_service = OrderService(db)

    try:
        order = await order_service.cancel_order(order_id, current_user)
        return order
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@orders_router.get("/orders/{order_id}", response_model=OrderSchema)
async def api_get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Получить один заказ по id."""
    order_service = OrderService(db)

    try:
        order, _is_admin = await order_service.get_order_for_user(
            order_id, current_user
        )
        return order
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@orders_router.post("/orders/{order_id}/confirm", response_model=OrderSchema)
async def api_confirm_order_payment(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Подтвердить оплату заказа."""
    order_service = OrderService(db)

    try:
        order = await order_service.confirm_payment(order_id, current_user.id)
        return order
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@orders_router.get("/orders/payment/{order_id}", response_model=dict)
async def api_get_payment_info(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Данные для страницы оплаты заказа."""
    order_service = OrderService(db)

    try:
        order = await order_service.get_order_for_payment(order_id, current_user.id)
        return {
            "order_id": order.id,
            "total_amount": float(order.total_amount),
            "status": order.status,
            "items_count": len(order.items),
        }
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )


@orders_router.post(
    "/orders/{order_id}/items/{item_id}/return", response_model=OrderActionResponse
)
async def api_return_order_item(
    order_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Вернуть позицию заказа на склад."""
    order_service = OrderService(db)

    try:
        await order_service.return_item_to_stock(order_id, item_id, current_user)
        updated_order = await order_service.get_order_with_items(order_id)
        if updated_order:
            return OrderActionResponse(message="Товар возвращён", order=updated_order)
        return OrderActionResponse(
            message="Товар возвращён, заказ удалён (не осталось позиций)",
            order=None,
            order_deleted=True,
        )
    except (BusinessError, OrderNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@orders_router.post("/orders/{order_id}/items", response_model=OrderSchema)
async def api_add_item_to_order(
    order_id: int,
    data: OrderItemAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Добавить позицию в заказ."""
    order_service = OrderService(db)

    try:
        await order_service.add_item_to_order(
            order_id=order_id,
            item_id=data.product_id,
            quantity=data.quantity,
            current_user=current_user,
        )
        order, _is_admin = await order_service.get_order_for_user(
            order_id, current_user
        )
        return order
    except (OrderNotFoundError, BusinessError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
