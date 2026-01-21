from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, status, HTTPException, Request, Query, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy import delete, func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_user
from app.services.cart import get_cart_count
from app.core.deps import get_db
from app.models.products import Product
from app.models.cart_items import CartItem as CartItemModel
from app.models.orders import Order as OrderModel, OrderItem as OrderItemModel
from app.models.users import User as UserModel
from app.schemas.order import Order as OrderSchema, OrderList
from app.services.cart_service import CartService
from app.core.config import templates

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)

async def _load_order_with_items(db: AsyncSession, order_id: int) -> OrderModel | None:
    result = await db.scalars(
        select(OrderModel)
        .options(
            selectinload(OrderModel.items).selectinload(OrderItemModel.product),
        )
        .where(OrderModel.id == order_id)
    )
    return result.first()


@router.post("/checkout", response_model=OrderSchema, status_code=status.HTTP_201_CREATED)
async def checkout_order(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Создаёт заказ на основе текущей корзины пользователя.
    Сохраняет позиции заказа, вычитает остатки и очищает корзину.
    """
    cart_result = await db.scalars(
        select(CartItemModel)
        .options(selectinload(CartItemModel.product))
        .where(CartItemModel.user_id == current_user.id)
        .order_by(CartItemModel.id)
    )
    cart_items = cart_result.all()
    if not cart_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    order = OrderModel(user_id=current_user.id)
    total_amount = Decimal("0")

    for cart_item in cart_items:
        product = cart_item.product
        if not product or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {cart_item.product_id} is unavailable",
            )
        if product.stock < cart_item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough stock for product {product.name}",
            )

        unit_price = product.price
        if unit_price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {product.name} has no price set",
            )
        total_price = unit_price * cart_item.quantity
        total_amount += total_price

        order_item = OrderItemModel(
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            unit_price=unit_price,
            total_price=total_price,
        )
        order.items.append(order_item)

        product.stock -= cart_item.quantity

    order.total_amount = total_amount
    db.add(order)

    await db.execute(delete(CartItemModel).where(CartItemModel.user_id == current_user.id))
    await db.commit()

    created_order = await _load_order_with_items(db, order.id)
    if not created_order:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось загрузить созданный заказ",
        )

    pay_url = request.url_for("payment_page", order_id=created_order.id)
    return RedirectResponse(url=pay_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/payment/{order_id}", response_class=HTMLResponse, name="payment_page")
async def payment_page(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    order = await _load_order_with_items(db, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    return templates.TemplateResponse(
        "payment.html",
        {"request": request, "order": order},
    )
    

@router.get("/cart", response_class=HTMLResponse)
async def cart_page(
    request: Request, 
    db: AsyncSession = Depends(get_db), 
    current_user: UserModel = Depends(get_current_user)
):
    cart_result = await db.scalars(
        select(CartItemModel)
        .options(selectinload(CartItemModel.product))
        .where(CartItemModel.user_id == current_user.id)
    )
    cart_items = cart_result.all()
    total = sum(item.product.price * item.quantity for item in cart_items if item.product)


    return templates.TemplateResponse("cart.html", {
        "request": request, 
        "cart_items": cart_items, 
        "total": total,
        "current_user": current_user,

    })


@router.post("/cart/add")
async def add_to_cart(
    product_id: int = Form(...),
    quantity: int = Form(1),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    result = await db.scalars(
        select(Product).where(Product.id == product_id, Product.is_active.is_(True))
    )
    product = result.first()
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Товар не найден")

    cart_result = await db.scalars(
        select(CartItemModel)
        .where(
            and_(
                CartItemModel.user_id == current_user.id,
                CartItemModel.product_id == product_id
            )
        )
    )
    cart_item = cart_result.first()

    if cart_item:
        cart_item.quantity += quantity
        cart_item.updated_at = datetime.utcnow()
    else:
        cart_item = CartItemModel(
            user_id=current_user.id,
            product_id=product_id,
            quantity=quantity
        )
        db.add(cart_item)

    await db.commit()
    await db.refresh(cart_item)

    return RedirectResponse(url="/products", status_code=303)


@router.post("/cart/remove/{item_id}")
async def remove_from_cart(
    request: Request,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    result = await db.scalars(select(CartItemModel).where(and_(CartItemModel.id == item_id, CartItemModel.user_id == current_user.id)))
    cart_item = result.first()
    if not cart_item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Элемент корзины не найден")

    await db.delete(cart_item)
    await db.commit()

    url = request.url_for("cart_page")
    return RedirectResponse(url=url, status_code=303)



@router.get("/", response_model=OrderList)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):

    total = await db.scalar(
        select(func.count(OrderModel.id)).where(OrderModel.user_id == current_user.id)
    )
    result = await db.scalars(
        select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.product))
        .where(OrderModel.user_id == current_user.id)
        .order_by(OrderModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orders = result.all()

    return OrderList(items=orders, total=total or 0, page=page, page_size=page_size)


@router.get("/{order_id}", response_class=HTMLResponse)
async def get_order_html(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    cart_count: int = Depends(get_cart_count),
):
    order = await _load_order_with_items(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    is_admin = current_user.role == 'seller'
    
    if not is_admin and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к чужому заказу")
    
    if is_admin:
        await db.refresh(order, ['user'])
    
    return templates.TemplateResponse(
        "/order/order_detail.html",
        {
            "request": request,
            "order": order,
            "is_admin": is_admin, 
            "current_user": current_user,
            "cart_count": cart_count,
            "is_own_order": order.user_id == current_user.id,
        }
    )
    

@router.post("/cart/api/add")
async def add_to_cart_api(product_id: int = Form(...), quantity: int = Form(1), db: AsyncSession = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    product = await db.scalar(select(Product).where(and_(Product.id == product_id, Product.is_active.is_(True))))
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    cart_item = await db.scalar(select(CartItemModel).where(and_(CartItemModel.user_id == current_user.id, CartItemModel.product_id == product_id)))
    
    final_qty = quantity
    if cart_item:
        final_qty = min(cart_item.quantity + quantity, product.stock or 0)  # + и обрезка!
        cart_item.quantity = final_qty
        cart_item.updated_at = datetime.utcnow()
    else:
        final_qty = min(quantity, product.stock or 0)
        cart_item = CartItemModel(user_id=current_user.id, product_id=product_id, quantity=final_qty)
        db.add(cart_item)
    
    await db.commit()
    await db.refresh(cart_item)
    return {"quantity": final_qty}


@router.post("/cart/api/set")
async def set_cart_quantity_api(product_id: int = Form(...), quantity: int = Form(...), 
                            db: AsyncSession = Depends(get_db), 
                            current_user: UserModel = Depends(get_current_user)):
    product_result = await db.scalars(select(Product).where(and_(Product.id == product_id, Product.is_active.is_(True))))
    product = product_result.first()
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Товар не найден")

    # **ОБРЕЗАЕМ ДО STOCK ПЕРЕД ВСЁМ**
    final_quantity = min(quantity, product.stock or 0)
    
    cart_result = await db.scalars(select(CartItemModel).where(
        and_(CartItemModel.user_id == current_user.id, CartItemModel.product_id == product_id)))
    cart_item = cart_result.first()
    
    if final_quantity == 0:
        if cart_item:
            await db.delete(cart_item)
        await db.commit()
        return {"quantity": 0}
    
    if cart_item:
        cart_item.quantity = final_quantity
        cart_item.updated_at = datetime.utcnow()
        db.add(cart_item)
    else:
        cart_item = CartItemModel(user_id=current_user.id, product_id=product_id, quantity=final_quantity)
        db.add(cart_item)
    
    await db.commit()
    await db.refresh(cart_item)
    return {"quantity": cart_item.quantity}


@router.post("/{order_id}/items/{item_id}/return", response_class=HTMLResponse)
async def return_order_item_to_stock(
    order_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):

    order_item = await db.scalar(
        select(OrderItemModel)
        .options(selectinload(OrderItemModel.product))
        .options(selectinload(OrderItemModel.order))
        .where(
            OrderItemModel.id == item_id, 
            OrderItemModel.order_id == order_id
        )
    )
    if not order_item:
        raise HTTPException(404, "Позиция не найдена")
    
    if order_item.order.user_id != current_user.id and current_user.role != 'seller':
        raise HTTPException(403, "Нет прав")
    
    product = order_item.product
    qty = order_item.quantity
    order = order_item.order

    product.stock += qty
    
    await db.delete(order_item)
    await db.commit()
    await db.refresh(product, ["stock"])
    
    order = await _load_order_with_items(db, order_id)
    await db.commit()
    
    msg = f"{product.name} ({qty}шт) возвращен на склад"
    return RedirectResponse(
        f"/orders/{order_id}?message={msg.replace(' ', '+')}&message_type=success", 
        status_code=303
    )
