from fastapi import APIRouter, Depends, status, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.deps import get_db
from app.core.config import templates

from app.models.users import User as UserModel
from app.models.products import Product

from app.schemas.order import Order as OrderSchema

from app.services.cart import get_cart_count
from app.services.order_service import OrderService
from app.services.cart_service import CartService
from app.services.product_service import ProductService


router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "/checkout", response_model=OrderSchema, status_code=status.HTTP_201_CREATED
)
async def checkout_order(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    order_svc = OrderService(db)
    created_order = await order_svc.get_checkout_order(current_user)
    pay_url = request.url_for("payment_page", order_id=created_order)
    return RedirectResponse(url=pay_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/payment/{order_id}", response_class=HTMLResponse, name="payment_page")
async def payment_page(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    order_svc = OrderService(db)
    order = await order_svc.get_order_for_payment(order_id, current_user.id)

    return templates.TemplateResponse(
        "payment.html", {"request": request, "order": order}
    )


@router.get("/cart", response_class=HTMLResponse)
async def cart_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    cart_svc = CartService(db)
    cart_items, total = await cart_svc.get_cart_page(current_user, ordered=False)
    return templates.TemplateResponse(
        "cart.html",
        {
            "request": request,
            "cart_items": cart_items,
            "total": total,
            "current_user": current_user,
        },
    )


@router.post("/cart/remove/{item_id}")
async def remove_from_cart(
    request: Request,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    cart_svc = CartService(db)
    await cart_svc.remove_cart_item_by_id(current_user.id, item_id)
    url = request.url_for("cart_page")
    return RedirectResponse(url=url, status_code=303)


@router.get("/{order_id}", response_class=HTMLResponse)
async def order_page(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    cart_count: int = Depends(get_cart_count),
):
    order_svc = OrderService(db)
    order, is_admin = await order_svc.get_order_for_user(order_id, current_user)
    available_products = (
        await db.scalars(
            select(Product).where(Product.stock > 0).order_by(Product.name)
        )
    ).all()
    return templates.TemplateResponse(
        "/order/order_detail.html",
        {
            "request": request,
            "order": order,
            "is_admin": is_admin,
            "current_user": current_user,
            "cart_count": cart_count,
            "is_own_order": order.user_id == current_user.id,
            "available_products": available_products,
        },
    )


@router.post("/cart/api/add")
async def add_to_cart_api(
    product_id: int = Form(...),
    quantity: int = Form(1),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    product_svc = ProductService(db)
    cart_svc = CartService(db)
    product = await product_svc.crud.get_product_active(product_id)
    final_qty = await cart_svc.cart_update_api(
        current_user.id, product_id, quantity, product, add_mode=True
    )
    return {"quantity": final_qty}


@router.post("/cart/api/set")
async def set_cart_quantity_api(
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    product_svc = ProductService(db)
    cart_svc = CartService(db)
    product = await product_svc.crud.get_product_active(product_id)
    final_qty = await cart_svc.cart_update_api(
        current_user.id, product_id, quantity, product, add_mode=False
    )
    return {"quantity": final_qty}


@router.post("/{order_id}/items/{item_id}/return", response_class=HTMLResponse)
async def return_order_item_to_stock(
    order_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    order_svc = OrderService(db)
    redirect_path = await order_svc.return_item_to_stock(
        order_id, item_id, current_user
    )
    return RedirectResponse(f"/{redirect_path}", status_code=303)


@router.post("/{order_id}/items/", response_class=HTMLResponse)
async def add_item_to_order(
    order_id: int,
    item_id: int = Form(..., description="ID товара"),
    quantity: int = Form(1, ge=1, le=99),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    order_svc = OrderService(db)
    redirect_path = await order_svc.add_item_to_order(
        order_id, item_id, quantity, current_user
    )
    return RedirectResponse(f"/{redirect_path}", status_code=303)
