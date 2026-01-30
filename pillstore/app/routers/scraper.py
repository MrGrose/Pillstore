
from decimal import Decimal
from fastapi import APIRouter, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.services.scraper_url import IHerbProductParser

from app.core.security import get_current_seller
from app.services.utils import save_image_from_url

from app.models.users import User
from app.models.categories import Category 
from app.models.products import Product

router = APIRouter(prefix="/admin")

@router.post("/products/iherb-import")
async def iherb_import(
    url: str = Form(...),
    tab: str = Form("products"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_seller),
):
    parser = IHerbProductParser()
    product_data = parser.parse_product(url)

    if not product_data:
        raise HTTPException(400, "Не удалось распарсить товар iHerb")
    
    
    # ✅ 1. ПРОВЕРКА ДУБЛИКАТА
    existing = await db.scalars(select(Product).where(Product.url == product_data.url))
    if existing.first():
        msg = f"Товар {product_data.name} уже существует"
        return RedirectResponse(
            f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type=warning",
            status_code=303,
        )
    
    # ✅ 2. СОЗДАЕМ КАТЕГОРИИ (БЕЗ commit в цикле!)
    categories = []
    parent = None
    
    if product_data.category_path:
        print(f"[DEBUG] category_path: {product_data.category_path}")
        for cat_name in product_data.category_path[1:]:
            cat_name = cat_name.strip()
            if cat_name and len(cat_name) > 1:
                # Ищем существующую
                cat_result = await db.scalars(
                    select(Category).where(
                        or_(Category.name == cat_name, Category.name.ilike(f"%{cat_name}%"))
                    )
                )
                cat = cat_result.first()
                
                if not cat:
                    cat = Category(
                        name=cat_name,
                        parent_id=parent.id if parent else None,
                        is_active=True
                    )
                    db.add(cat)
                
                categories.append(cat)
                parent = cat
    


    # ✅ 3. Картинка
    image_url = None
    if product_data.images:
        img_urls = product_data.images if isinstance(product_data.images, list) else [product_data.images]
        image_url = await save_image_from_url(img_urls[0])
    
    # ✅ 4. Создаем товар
    short_name = (product_data.name or product_data.name_en or "Без названия")[:100]
    price_fixed = Decimal(str(round(product_data.price or 0.0, 2)))
    
    db_product = Product(
        name=short_name,
        name_en=product_data.name_en or "",
        brand=product_data.brand or "",
        price=price_fixed,
        url=product_data.url or "",
        image_url=image_url,
        description_left=product_data.description_left or "",
        description_right=product_data.description_right or "",
        stock=product_data.stock or 10,
        seller_id=current_user.id,
        is_active=True,
        category_id=[cat.id for cat in categories],  # ✅ list[int]
        categories=categories,                        # ✅ relation
        mpn=product_data.mpn
    )
    
    db.add(db_product)
    await db.commit()  # ✅ ОДИН commit для всего!
    
    print(f"[SUCCESS] Товар ID={db_product.id}")
    print(f"[SUCCESS] Категории ID: {[cat.id for cat in categories]}")  # ✅ Без .name!
    
    msg = f"ID {db_product.id} {short_name} импортирован"
    return RedirectResponse(
        f"/admin?tab={tab}&message={msg.replace(' ', '+')}&message_type=success",
        status_code=303,
    )