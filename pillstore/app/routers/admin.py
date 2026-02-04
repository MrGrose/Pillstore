from datetime import datetime
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
    Form,
    Query,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.config import templates
from app.core.security import get_current_seller

from app.models.users import User

from app.services.cart import get_cart_count
from app.services.category_service import CategoryService
from app.services.admin_service import AdminService
from app.services.user_service import UserService

from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product_service import ProductService

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
    cart_count: int = Depends(get_cart_count),
    tab: str = Query("dashboard"),
    message: str = Query(None),
    message_type: str = Query("info"),
    status_filter: str = Query(None),
    page_active: int = Query(1, ge=1),
    page_size_active: int = Query(20, ge=1, le=100),
    search_product: str | None = Query(None),
    category_id: int = Query(None),
    page_inactive: int = Query(1, ge=1),
    page_size_inactive: int = Query(20, ge=1, le=100),
):
    product_svc = ProductService(db)
    pagination_active = await product_svc.get_products_page_active(
        page_active, page_size_active, search_product, request, category_id
    )
    pagination_inactive = await product_svc.get_products_page_inactive(
        page_inactive, page_size_inactive, search_product, request, category_id
    )
    flash_message = {"text": message, "type": message_type} if message else None
    admin_svc = AdminService(db)
    dashboard_stats = await admin_svc.get_admin_page(status_filter)

    return templates.TemplateResponse(
        "/admin/admin.html",
        {
            "request": request,
            **dashboard_stats,
            "cart_count": cart_count,
            "current_user": current_user,
            "tab": tab,
            "flash_message": flash_message,
            "status_filter": status_filter,
            "products": pagination_active.items,
            "products_not_active": pagination_inactive.items,
            "pagination_active": pagination_active,
            "pagination_inactive": pagination_inactive,
            "search": search_product,
            "active_category_id": category_id,
            "pagination": pagination_active,
        },
    )


@router.post("/orders/{order_id}/status", response_class=HTMLResponse)
async def update_order_status(
    order_id: int,
    new_status: str = Form(...),
    db: AsyncSession = Depends(get_db),
    tab: str = Query("orders"),
    status_filter: str = Query(None),
):
    admin_svc = AdminService(db)
    await admin_svc.order_status_admin(order_id, new_status)
    url = f"/admin?tab={tab}&message=Статус заказа {order_id} изменен на {new_status}&message_type=success"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/orders/{order_id}/delete", response_class=HTMLResponse)
async def delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    tab: str = Query("orders"),
    status_filter: str = Query(None),
):
    admin_svc = AdminService(db)
    await admin_svc.remove_order_admin(order_id)
    url = f"/admin?tab={tab}&message=Заказ {order_id} удален, товары возвращены&message_type=success"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/products/{product_id}/delete")
async def delete_product(
    product_id: int,
    tab: str = Form("products"),
    db: AsyncSession = Depends(get_db),
):
    admin_svc = AdminService(db)
    message = await admin_svc.remove_product_admin(product_id)
    return RedirectResponse(
        f"/admin?tab={tab}&message={message.replace(' ', '+')}&message_type=success",
        status_code=303,
    )


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_form(
    request: Request,
    product_id: int,
    tab: str = Query("products"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    category_svc = CategoryService(db)
    admin_svc = AdminService(db)
    product = await admin_svc.product_crud.get_by_id_with_categories(product_id)
    categories = await category_svc.get_all_categories()
    context = {
        "request": request,
        "product": product,
        "tab": tab,
        "action_url": f"/admin/products/{product_id}",
        "categories": categories,
        "current_user": current_user,
        "created_at_iso": (
            product.created_at.strftime("%Y-%m-%dT%H:%M")
            if product and product.created_at
            else ""
        ),
        "expiry_at_iso": (
            product.expiry_at.strftime("%Y-%m-%d")
            if product and product.expiry_at
            else ""
        ),
        "created_at_display": (
            product.created_at.strftime("%d.%m.%Y %H:%M")
            if product and product.created_at
            else "Не указана"
        ),
        "expiry_at_display": (
            product.expiry_at.strftime("%d.%m.%Y")
            if product and product.expiry_at
            else "Не указан"
        ),
    }
    return templates.TemplateResponse("admin/product_edit.html", context)


@router.get("/products/new", response_class=HTMLResponse)
async def new_product_form(
    request: Request,
    tab: str = Query("products"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    category_svc = CategoryService(db)
    categories = await category_svc.get_all_categories()
    return templates.TemplateResponse(
        "admin/product_edit.html",
        {
            "request": request,
            "product": None,
            "tab": tab,
            "action_url": "/admin/products",
            "categories": categories,
            "current_user": current_user,
        },
    )


@router.post("/products/{product_id}", response_class=HTMLResponse)
async def admin_product_update(
    product_id: int,
    category_ids: list[int] = Form([]),
    tab: str = Form("products"),
    name: str = Form(...),
    name_en: str = Form(""),
    brand: str = Form(None),
    price: float = Form(...),
    stock: int = Form(0),
    description_left: str = Form(None),
    description_right: str = Form(None),
    is_active: bool = Form(True),
    image: UploadFile | None = File(None),
    created_at: str = Form(None),
    expiry_at: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    parsed_created_at = datetime.fromisoformat(created_at) if created_at else None
    parsed_expiry_at = datetime.fromisoformat(expiry_at).date() if expiry_at else None
    data = ProductUpdate(
        name=name,
        name_en=name_en,
        brand=brand or "",
        price=price,
        stock=stock,
        is_active=is_active,
        category_ids=category_ids,
        description_left=description_left or "",
        description_right=description_right or "",
        created_at=parsed_created_at,
        expiry_at=parsed_expiry_at,
    )
    admin_svc = AdminService(db)
    msg, msg_type = await admin_svc.update_product_admin(
        product_id, data, category_ids, image
    )
    await db.commit()
    return RedirectResponse(
        f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type={msg_type}",
        status_code=303,
    )


@router.post("/products", response_class=HTMLResponse)
async def admin_product_create(
    category_ids: list[int] = Form([]),
    tab: str = Form("products"),
    name: str = Form(...),
    name_en: str = Form(""),
    brand: str = Form(None),
    price: float = Form(...),
    stock: int = Form(0),
    description_left: str = Form(None),
    description_right: str = Form(None),
    is_active: bool = Form(True),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    data = ProductCreate(
        name=name,
        name_en=name_en,
        brand=brand,
        price=Decimal(price),
        description_left=description_left,
        description_right=description_right,
        category_id=category_ids if category_ids else [],
        stock=stock,
        is_active=is_active,
        seller_id=current_user.id,
    )
    admin_svc = AdminService(db)
    msg, msg_type = await admin_svc.create_product_admin(data, image)
    return RedirectResponse(
        f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type={msg_type}",
        status_code=303,
    )


@router.get("/users/new", response_class=HTMLResponse)
async def new_user_form(
    request: Request,
    tab: str = Query("users"),
    current_user: User = Depends(get_current_seller),
):
    return templates.TemplateResponse(
        "admin/user_edit.html",
        {
            "request": request,
            "user": None,
            "tab": tab,
            "action_url": "/admin/users/new?tab=users",
            "current_user": current_user,
        },
    )


@router.post("/users/new", response_class=HTMLResponse)
async def create_user(
    email: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    tab: str = Form("users"),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    user = await user_service.create_admin_user(email, password, role)
    if isinstance(user, tuple):
        error_url, status_code = user
        return RedirectResponse(error_url, status_code=status_code)
    msg = f"Пользователь {user} создан"
    return RedirectResponse(
        f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type=success",
        status_code=303,
    )


@router.get("/users/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_form(
    request: Request,
    user_id: int,
    tab: str = Query("users"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    user_service = UserService(db)
    try:
        user = await user_service.get_user_for_edit(user_id)
    except HTTPException:
        return RedirectResponse(
            f"/admin/error-404?title=Пользователь не найден&message=ID {user_id} не найден&tab=users",
            status_code=302,
        )
    return templates.TemplateResponse(
        "admin/user_edit.html",
        {
            "request": request,
            "user": user,
            "tab": tab,
            "action_url": f"/admin/users/{user_id}?tab={tab}",
            "current_user": current_user,
        },
    )


@router.post("/users/{user_id}", response_class=HTMLResponse)
async def update_user(
    user_id: int,
    email: str = Form(...),
    role: str = Form(...),
    password: str = Form(None),
    tab: str = Form("users"),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    user = await user_service.update_admin_user(user_id, email, password, role)
    if isinstance(user, tuple):
        error_url, status_code = user
        return RedirectResponse(error_url, status_code=status_code)
    msg = f"Пользователь {user} обновлен"
    return RedirectResponse(
        f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type=success",
        status_code=303,
    )


@router.post("/users/{user_id}/delete", response_class=HTMLResponse)
async def delete_user(
    user_id: int,
    tab: str = Form("users"),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    result = await user_service.delete_admin_user(user_id)
    if isinstance(result, tuple):
        error_url, status_code = result
        return RedirectResponse(error_url, status_code=status_code)
    return RedirectResponse(
        f"/admin?tab={tab}&message={result.replace(' ', '+')}&message_type=success",
        status_code=303,
    )
