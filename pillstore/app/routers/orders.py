from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import templates
from app.core.deps import get_db
from app.core.security import get_current_user
from app.db_crud.order_crud import CrudOrder
from app.models.orders import Order
from app.models.products import Product
from app.models.users import User as UserModel
from app.services.cart import get_cart_count
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.product_service import ProductService


router = APIRouter(prefix="/orders")


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    cart_count: int = Depends(get_cart_count),
):
    cart_svc = CartService(db)
    cart_items, total = await cart_svc.get_cart_page(current_user, ordered=False)
    return templates.TemplateResponse(
        "order/checkout.html",
        {
            "request": request,
            "cart_items": cart_items,
            "total": total,
            "current_user": current_user,
            "cart_count": cart_count,
        },
    )


@router.post("/checkout", response_class=HTMLResponse)
async def checkout_order(
    request: Request,
    contact_phone: str = Form(..., min_length=5),
    personal_data_consent: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    cart_count: int = Depends(get_cart_count),
):
    if personal_data_consent != "1":
        cart_svc = CartService(db)
        cart_items, total = await cart_svc.get_cart_page(current_user, ordered=False)
        return templates.TemplateResponse(
            "order/checkout.html",
            {
                "request": request,
                "cart_items": cart_items,
                "total": total,
                "current_user": current_user,
                "cart_count": cart_count,
                "contact_phone": contact_phone,
                "flash_error": "Необходимо дать согласие на обработку персональных данных.",
            },
            status_code=400,
        )
    cart_svc = CartService(db)
    cart_items, total = await cart_svc.get_cart_page(current_user, ordered=False)
    if not cart_items:
        return RedirectResponse("/orders/cart", status_code=303)
    order_crud = CrudOrder(db, Order)
    product_ids = [item.product_id for item in cart_items]
    reserved_map = await order_crud.get_pending_reserved_map(product_ids)
    items_data = []
    for item in cart_items:
        if not item.product or not item.product.is_active:
            continue
        reserved = reserved_map.get(item.product_id, 0)
        available = (item.product.stock or 0) - reserved
        if available < item.quantity:
            continue
        unit_cost = getattr(item.product, "cost", None) or 0
        items_data.append({
            "product_id": item.product_id,
            "name": item.product.name,
            "quantity": item.quantity,
            "unit_price": float(item.product.price),
            "unit_cost": float(unit_cost),
        })
    if not items_data:
        return RedirectResponse("/orders/cart", status_code=303)
    request.session["checkout"] = {
        "items": items_data,
        "total": float(total),
        "contact_phone": contact_phone.strip(),
        "personal_data_consent": True,
    }
    return RedirectResponse("/orders/payment", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/payment", response_class=HTMLResponse)
async def payment_from_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    cart_count: int = Depends(get_cart_count),
):
    checkout = request.session.get("checkout")
    if not checkout or not checkout.get("items"):
        return RedirectResponse("/orders/cart", status_code=303)
    return templates.TemplateResponse(
        "payment.html",
        {
            "request": request,
            "order": None,
            "checkout": checkout,
            "current_user": current_user,
            "cart_count": cart_count,
        },
    )


@router.post("/confirm", response_class=HTMLResponse)
async def confirm_order_from_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    checkout = request.session.pop("checkout", None)
    if not checkout or not checkout.get("items"):
        return RedirectResponse("/orders/cart", status_code=303)
    order_svc = OrderService(db)
    try:
        order_id = await order_svc.create_order_from_checkout(current_user, checkout)
    except Exception:
        request.session["checkout"] = checkout
        return RedirectResponse(
            "/orders/payment?error=1", status_code=303
        )
    return RedirectResponse(
        f"/orders/{order_id}?confirmed=true", status_code=303
    )


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
        "payment.html",
        {
            "request": request,
            "order": order,
            "current_user": current_user,
        },
    )


@router.post("/{order_id}/confirm")
async def confirm_order_payment(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    order_service = OrderService(db)
    await order_service.confirm_payment(order_id, current_user.id)
    return RedirectResponse(f"/orders/{order_id}?confirmed=true", status_code=303)


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


@router.get("/{order_id}/receipt", response_class=HTMLResponse)
async def order_receipt(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    order_svc = OrderService(db)
    order, _ = await order_svc.get_order_for_user(order_id, current_user)
    if not order:
        return RedirectResponse("/orders/cart", status_code=302)
    from app.core.receipt_config import (
        RECEIPT_TITLE,
        RECEIPT_FOOTER,
        RECEIPT_TOTAL_LABEL,
        build_receipt_meta,
        build_receipt_table,
        build_receipt_total,
    )
    receipt_headers, receipt_rows = build_receipt_table(order)
    return templates.TemplateResponse(
        "order/receipt.html",
        {
            "request": request,
            "current_user": current_user,
            "order": order,
            "receipt_title": RECEIPT_TITLE,
            "receipt_meta": build_receipt_meta(order),
            "receipt_headers": receipt_headers,
            "receipt_rows": receipt_rows,
            "receipt_total_label": RECEIPT_TOTAL_LABEL,
            "receipt_total": build_receipt_total(order),
            "receipt_footer": RECEIPT_FOOTER,
        },
    )


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
