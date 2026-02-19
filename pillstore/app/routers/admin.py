import json
from datetime import datetime
from decimal import Decimal

from app.core.admin_redirect import redirect_admin
from app.core.config import templates
from app.core.deps import get_db
from app.core.security import get_current_seller
from app.models.users import User
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.admin_service import AdminService
from app.services.cart import get_cart_count
from app.services.category_service import CategoryService
from app.services.product_service import ProductService
from app.services.user_service import UserService
from app.utils.description_parser import (
    DEFAULT_DESCRIPTION_SECTIONS,
    RIGHT_SECTION_TITLES,
    formatted_description,
)
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
    cart_count: int = Depends(get_cart_count),
    tab: str = Query("dashboard"),
    period: str = Query("30d"),
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
    dashboard_data = await admin_svc.get_dashboard_data(period)
    dashboard_data["trend_json"] = json.dumps(dashboard_data["trend"])

    return templates.TemplateResponse(
        "/admin/admin.html",
        {
            "request": request,
            **dashboard_stats,
            "dashboard": dashboard_data,
            "period": period,
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
    current_user: User = Depends(get_current_seller),
    tab: str = Query("orders"),
    status_filter: str = Query(None),
):
    admin_svc = AdminService(db)
    await admin_svc.order_status_admin(order_id, new_status)
    return redirect_admin(
        tab,
        message=f"Статус заказа {order_id} изменен на {new_status}",
        message_type="success",
        status_filter=status_filter,
    )


@router.post("/orders/{order_id}/delete", response_class=HTMLResponse)
async def delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
    tab: str = Query("orders"),
    status_filter: str = Query(None),
):
    admin_svc = AdminService(db)
    await admin_svc.remove_order_admin(order_id)
    return redirect_admin(
        tab,
        message=f"Заказ {order_id} удален, товары возвращены",
        message_type="success",
        status_filter=status_filter,
    )


@router.post("/products/{product_id}/delete")
async def delete_product(
    product_id: int,
    tab: str = Form("products"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    admin_svc = AdminService(db)
    msg = await admin_svc.remove_product_admin(product_id)
    return redirect_admin(tab, message=msg, message_type="success")


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_form(
    request: Request,
    product_id: int,
    tab: str = Query("products"),
    message: str = Query(None),
    message_type: str = Query("info"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    category_svc = CategoryService(db)
    admin_svc = AdminService(db)
    product = await admin_svc.product_crud.get_by_id_with_categories(product_id)
    categories = await category_svc.get_all_categories()
    batches = await admin_svc.get_batches_for_product(product_id)
    product_description = await formatted_description(product) if product else {}
    flash_message = {"text": message, "type": message_type} if message else None
    context = {
        "request": request,
        "product": product,
        "tab": tab,
        "flash_message": flash_message,
        "action_url": f"/admin/products/{product_id}",
        "categories": categories,
        "batches": batches,
        "current_user": current_user,
        "product_description": product_description,
        "right_section_titles": RIGHT_SECTION_TITLES,
        "created_at_iso": (
            product.created_at.strftime("%Y-%m-%dT%H:%M")
            if product and product.created_at
            else ""
        ),
        "created_at_display": (
            product.created_at.strftime("%d.%m.%Y %H:%M")
            if product and product.created_at
            else "Не указана"
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
    product_description = {name: [] for name in DEFAULT_DESCRIPTION_SECTIONS}
    return templates.TemplateResponse(
        "admin/product_edit.html",
        {
            "request": request,
            "product": None,
            "tab": tab,
            "action_url": "/admin/products",
            "categories": categories,
            "current_user": current_user,
            "product_description": product_description,
            "right_section_titles": RIGHT_SECTION_TITLES,
        },
    )


@router.post("/products/{product_id}/batches/{batch_id}/delete", response_class=HTMLResponse)
async def delete_product_batch(
    product_id: int,
    batch_id: int,
    tab: str = Query("products"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    admin_svc = AdminService(db)
    try:
        await admin_svc.delete_batch_admin(product_id=product_id, batch_id=batch_id)
    except Exception as e:
        return redirect_admin(
            tab,
            message=str(e),
            message_type="error",
            path=f"/admin/products/{product_id}/edit",
        )
    return redirect_admin(
        tab,
        message="Партия удалена",
        message_type="success",
        path=f"/admin/products/{product_id}/edit",
    )


def _build_description_from_section_lists(
    section_names: list[str], section_contents: list[str]
) -> tuple[str, str]:
    right_set = set(RIGHT_SECTION_TITLES)
    left_sections = []
    right_sections = []
    for name, content in zip(section_names, section_contents):
        name = (name or "").strip()
        lines = [s.strip() for s in (content or "").strip().split("\n") if s.strip()]
        if not name:
            continue
        sec = {"title": name, "content": lines if lines else [content.strip()]}
        if name in right_set:
            right_sections.append(sec)
        else:
            left_sections.append(sec)
    left_json = json.dumps(left_sections, ensure_ascii=False) if left_sections else ""
    right_json = json.dumps(right_sections, ensure_ascii=False) if right_sections else ""
    return left_json, right_json


@router.post("/products/{product_id}", response_class=HTMLResponse)
async def admin_product_update(
    request: Request,
    product_id: int,
    category_ids: list[int] = Form([]),
    tab: str = Form("products"),
    name: str = Form(...),
    name_en: str = Form(""),
    brand: str = Form(None),
    price: float = Form(...),
    cost: float = Form(0),
    stock: int = Form(0),
    url: str | None = Form(None),
    description_left: str = Form(None),
    description_right: str = Form(None),
    is_active: bool = Form(True),
    image: UploadFile | None = File(None),
    created_at: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    form = await request.form()
    sn = form.getlist("desc_section_name")
    sc = form.getlist("desc_section_content")
    if sn and sc and len(sn) == len(sc):
        description_left, description_right = _build_description_from_section_lists(sn, sc)
    else:
        description_left = description_left or ""
        description_right = description_right or ""
    parsed_created_at = datetime.fromisoformat(created_at) if created_at else None
    url_value = (url or "").strip() or None
    data = ProductUpdate(
        name=name,
        name_en=name_en,
        brand=brand or "",
        price=price,
        cost=cost,
        stock=stock,
        url=url_value,
        is_active=is_active,
        category_ids=category_ids,
        description_left=description_left,
        description_right=description_right,
        created_at=parsed_created_at,
    )
    admin_svc = AdminService(db)
    msg, msg_type = await admin_svc.update_product_admin(
        product_id, data, category_ids, image
    )
    await db.commit()
    return redirect_admin(tab, message=msg, message_type=msg_type)


@router.post("/products/{product_id}/batches", response_class=HTMLResponse)
async def add_product_batch(
    product_id: int,
    quantity: int = Form(...),
    expiry_date: str = Form(None),
    tab: str = Query("products"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    admin_svc = AdminService(db)
    try:
        await admin_svc.add_batch_admin(
            product_id=product_id,
            quantity=quantity,
            expiry_date=expiry_date or None,
        )
    except Exception as e:
        return redirect_admin(
            tab,
            message=str(e),
            message_type="error",
            path=f"/admin/products/{product_id}/edit",
        )
    return redirect_admin(
        tab,
        message="Партия добавлена",
        message_type="success",
        path=f"/admin/products/{product_id}/edit",
    )


@router.post("/products", response_class=HTMLResponse)
async def admin_product_create(
    request: Request,
    category_ids: list[int] = Form([]),
    tab: str = Form("products"),
    name: str = Form(...),
    name_en: str = Form(""),
    brand: str = Form(None),
    price: float = Form(...),
    cost: float = Form(0),
    stock: int = Form(0),
    batch_quantity: int = Form(0),
    batch_expiry_date: str = Form(None),
    url: str | None = Form(None),
    description_left: str = Form(None),
    description_right: str = Form(None),
    is_active: bool = Form(True),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    form = await request.form()
    sn = form.getlist("desc_section_name")
    sc = form.getlist("desc_section_content")
    if sn and sc and len(sn) == len(sc):
        description_left, description_right = _build_description_from_section_lists(sn, sc)
    else:
        description_left = description_left or ""
        description_right = description_right or ""
    url_value = (url or "").strip() or None
    effective_stock = 0 if batch_quantity and int(batch_quantity) > 0 else stock
    data = ProductCreate(
        name=name,
        name_en=name_en,
        brand=brand,
        price=Decimal(price),
        cost=Decimal(str(cost)),
        description_left=description_left,
        description_right=description_right,
        category_id=category_ids if category_ids else [],
        stock=effective_stock,
        is_active=is_active,
        url=url_value,
        seller_id=current_user.id,
    )
    admin_svc = AdminService(db)
    msg, product = await admin_svc.create_product_admin(data, image)
    if batch_quantity and int(batch_quantity) > 0:
        await admin_svc.add_batch_admin(
            product_id=product.id,
            quantity=int(batch_quantity),
            expiry_date=(batch_expiry_date or "").strip() or None,
        )
        msg = f"{msg}. Добавлено {batch_quantity} шт."
    return redirect_admin(tab, message=msg, message_type="success")


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
    current_user: User = Depends(get_current_seller),
):
    user_service = UserService(db)
    user = await user_service.create_admin_user(email, password, role)
    if isinstance(user, tuple):
        error_url, status_code = user
        return RedirectResponse(error_url, status_code=status_code)
    return redirect_admin(tab, message=f"Пользователь {user} создан", message_type="success")


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
    current_user: User = Depends(get_current_seller),
):
    user_service = UserService(db)
    user = await user_service.update_admin_user(user_id, email, password, role)
    if isinstance(user, tuple):
        error_url, status_code = user
        return RedirectResponse(error_url, status_code=status_code)
    return redirect_admin(tab, message=f"Пользователь {user} обновлен", message_type="success")


@router.post("/users/{user_id}/delete", response_class=HTMLResponse)
async def delete_user(
    user_id: int,
    tab: str = Form("users"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    user_service = UserService(db)
    result = await user_service.delete_admin_user(user_id)
    if isinstance(result, tuple):
        error_url, status_code = result
        return RedirectResponse(error_url, status_code=status_code)
    return redirect_admin(tab, message=result, message_type="success")
