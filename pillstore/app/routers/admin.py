from fastapi import APIRouter, Depends, status, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import inspect, select, func, update
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.core.config import templates

from app.models.products import Product as ProductModel
from app.models.orders import Order
from app.models.users import User as UserModel
from app.models.orders import Order as OrderModel, OrderItem

from app.core.security import get_current_user, get_current_seller, pwd_context
from app.services.cart import get_cart_count
from app.services.utils import remove_product_image, save_product_image

from app.services.category_service import CategoryService

router = APIRouter(prefix="/admin", tags=["Admin panel"])


@router.get("", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    cart_count: int = Depends(get_cart_count),
    tab: str = Query("dashboard"),
    message: str = Query(None),
    message_type: str = Query("info"),
    status_filter: str = Query(None),
):
    stats = {
        "total_orders": await db.scalar(select(func.count()).select_from(OrderModel)),
        "total_revenue": await db.scalar(
            select(func.sum(OrderModel.total_amount)).select_from(OrderModel)
        ) or 0,
        "total_products": await db.scalar(select(func.count()).select_from(ProductModel)),
        "pending_orders": await db.scalar(
            select(func.count()).select_from(OrderModel).where(OrderModel.status == 'pending')
        ),
    }
    
    flash_message = {"text": message, "type": message_type} if message else None
    
    db_products_active = await db.scalars(select(ProductModel).where(ProductModel.is_active == True))
    products_active = list(db_products_active.all())
    
    db_products_not_active = await db.scalars(select(ProductModel).where(ProductModel.is_active == False))
    products_not_active = list(db_products_not_active.all())
    
    users_result = await db.scalars(select(UserModel))
    users = list(users_result.all())

    user_order_counts = {}
    for user in users:
        count = await db.scalar(
            select(func.count(OrderModel.id)).where(OrderModel.user_id == user.id)
        )
        user_order_counts[user.id] = count
        
    orders_query = (
        select(OrderModel)
        .options(selectinload(OrderModel.user))
        .order_by(OrderModel.created_at.desc())
    )
    if status_filter and status_filter != "all":
        orders_query = orders_query.where(OrderModel.status == status_filter)
    
    orders_result = await db.scalars(orders_query)
    orders = orders_result.all()
    
    return templates.TemplateResponse(
        "/admin/admin.html",
        {
            "request": request,
            "stats": stats,
            "products": products_active,
            "products_not_active": products_not_active,
            "orders": orders,
            "users": users,
            "user_order_counts": user_order_counts,
            "cart_count": cart_count,
            "current_user": current_user,
            "tab": tab,
            "flash_message": flash_message,
            "status_filter": status_filter,
        }
    )
    
@router.post("/orders/{order_id}/status", response_class=HTMLResponse)
async def update_order_status(
    order_id: int,
    new_status: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    tab: str = Query("orders"),
    status_filter: str = Query(None), 
):
    order = await db.scalar(
        select(OrderModel).options(selectinload(OrderModel.items)).where(OrderModel.id == order_id)
    )
    if not order:
        raise HTTPException(404, "Заказ не найден")
    
    if new_status not in ['pending', 'paid', 'transit']:
        raise HTTPException(400, "Неверный статус")
    
    order.status = new_status
    await db.commit()
    
    url = f"/admin?tab={tab}&message=Статус заказа #{order_id} изменен на {new_status}&message_type=success"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=303)


@router.post("/orders/{order_id}/delete", response_class=HTMLResponse)
async def delete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    tab: str = Query("orders"),
    status_filter: str = Query(None),
):
    order = await db.scalar(
        select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItem.product))
        .where(OrderModel.id == order_id)
    )
    if not order:
        raise HTTPException(404, "Заказ не найден")
    
    for item in order.items:
        if item.product:
            item.product.stock += item.quantity
    
    await db.delete(order)
    await db.commit()
    for item in order.items:
        if item.product:
            await db.refresh(item.product, ["stock"])

    url = f"/admin?tab={tab}&message=Заказ #{order_id} удален, товары возвращены&message_type=success"
    if status_filter:
        url += f"&status_filter={status_filter}"
    return RedirectResponse(url, status_code=303)


@router.post("/products/{product_id}/delete")
async def delete_product(
    product_id: int,
    tab: str = Form("products"),
    db: AsyncSession = Depends(get_db),
):
    product = await db.scalar(select(ProductModel).where(ProductModel.id == product_id))
    
    if not product:
        return RedirectResponse(
            f"/admin?tab={tab}&message=Товар+не+найден&message_type=danger", 
            status_code=303
        )
    
    order_items_count = await db.scalar(
        select(func.count()).select_from(OrderItem).where(OrderItem.product_id == product_id)
    )
    
    if order_items_count > 0:
        product.is_active = False
        await db.commit()
        msg = "Товар помечен неактивным (используется в заказах)"
        msg_type = "warning"
    else:
        if product.image_url:
            remove_product_image(product.image_url)
        await db.delete(product)
        await db.commit()
        msg = "Товар удален"
        msg_type = "success"
    
    return RedirectResponse(
        f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type={msg_type}", 
        status_code=303
    )


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_form(
    request: Request,
    product_id: int,
    tab: str = Query("products"),   
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    category_svc = CategoryService(db)
    product = await db.scalar(
        select(ProductModel).where(ProductModel.id == product_id)
    )
    
    categories = await category_svc.get_all_categories()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    return templates.TemplateResponse("admin/product_edit.html", {
        "request": request,
        "product": product,
        "tab": tab,
        "action_url": f"/admin/products/{product_id}?tab={tab}",
        "categories": categories
    })

@router.get("/products/new", response_class=HTMLResponse)
async def new_product_form(
    request: Request,
    tab: str = Query("products"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):  
    category_svc = CategoryService(db)
    categories = await category_svc.get_all_categories()
    return templates.TemplateResponse("admin/product_edit.html", {
        "request": request,
        "product": None,
        "tab": tab,
        "action_url": f"/admin/products?tab={tab}",
        "categories": categories, 
    })
    
    
@router.post("/products", response_class=HTMLResponse)
async def admin_product_update(
    product_id_str: str | None = Form(None),
    category_ids: list[int] = Form([]),
    tab: str = Form("products"),
    name: str = Form(...),
    brand: str = Form(None),
    price: float = Form(...),
    stock: int = Form(0),
    description: str = Form(None), 
    is_active: bool = Form(True),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    category_id = category_ids if category_ids else None
    product_id = None
    if product_id_str and product_id_str.strip() and product_id_str.strip().isdigit():
        product_id = int(product_id_str)
        
    try:

        if product_id:
            product = await db.scalar(
                select(ProductModel)
                .where(ProductModel.id == product_id))
            
            if not product:
                raise HTTPException(404, "Товар не найден")
            
            product.name = name
            product.brand = brand or ""
            product.price = price
            product.stock = stock
            product.description = description or ""
            product.is_active = is_active
            product.category_id = category_ids
            
            if image and image.filename:
                if product.image_url:
                    remove_product_image(product.image_url)
                new_image_url = await save_product_image(image)
                product.image_url = new_image_url or ""
                
            msg = "Товар обновлен"
        else:
            product = ProductModel(
                name=name, 
                brand=brand or "", 
                price=price, 
                description=description or "",
                category_id=category_id, 
                stock=stock,
                is_active=is_active,
                image_url=await save_product_image(image) if image and image.filename else "",
                seller_id=current_user.id
            )
            db.add(product)
            msg = f"Товар '{name}' создан"

        await db.commit()
        saved = await db.scalar(select(ProductModel.category_id).where(ProductModel.id == product.id))

        msg_type = "success"
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        msg = f"Ошибка сохранения: {str(e)}"
        msg_type = "danger"
    
    return RedirectResponse(
        f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type={msg_type}", 
        status_code=303
    )
    
# USERS ---
@router.get("/users/new", response_class=HTMLResponse)
async def new_user_form(
    request: Request,
    tab: str = Query("users"),
    current_user: UserModel = Depends(get_current_seller),
):
    """ПОКАЗ ФОРМЫ нового пользователя"""
    return templates.TemplateResponse("admin/user_edit.html", {
        "request": request,
        "user": None, 
        "tab": tab,
        "action_url": "/admin/users/new?tab=users",
    })


@router.post("/users/new", response_class=HTMLResponse)
async def create_user(
    email: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    tab: str = Form("users"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    if await db.scalar(select(UserModel).where(UserModel.email == email)):
        raise HTTPException(400, "Email уже существует")
    
    user = UserModel(email=email, role=role)
    user.hashed_password = pwd_context.hash(password)
    db.add(user)
    await db.commit()
    
    msg = f"Пользователь {email} создан"
    return RedirectResponse(f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type=success", status_code=303)



@router.get("/users/{user_id}/edit", response_class=HTMLResponse, name="profile_page")
async def edit_user_form(
    request: Request,
    user_id: int,
    tab: str = Query("users"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    user = await db.scalar(select(UserModel).where(UserModel.id == user_id))
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    
    return templates.TemplateResponse("admin/user_edit.html", {
        "request": request,
        "user": user,
        "tab": tab,
        "action_url": f"/admin/users/{user_id}?tab={tab}",
    })


@router.post("/users/{user_id}", response_class=HTMLResponse)
async def update_user(
    user_id: int,
    email: str = Form(...),
    role: str = Form(...),
    password: str = Form(None),
    tab: str = Form("users"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    user = await db.scalar(select(UserModel).where(UserModel.id == user_id))
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    
    user.email = email
    user.role = role
    if password:
        user.hashed_password = pwd_context.hash(password)
    
    await db.commit()
    msg = f"Пользователь {email} обновлен"
    return RedirectResponse(f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type=success", status_code=303)


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_redirect(
    request: Request,
    user_id: int,
    tab: str = Query("users"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    return RedirectResponse(f"/admin/users/{user_id}/edit?tab={tab}", status_code=303)