from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import (
    get_current_seller,
    get_current_user_import,
    get_current_user_optional,
)
from app.exceptions.handlers import ProductNotFoundError
from app.models.categories import Category
from app.models.products import Product
from app.models.users import User as UserModel
from app.schemas.product import (
    ProductCreateAPI,
    ProductImportList,
    ProductListResponse,
    ProductSchema,
    ProductStockResponse,
    ProductUpdateAPI,
)
from app.services.product_service import ProductService
from app.utils.utils import save_image_from_url

product_router = APIRouter(prefix="/api/v2", tags=["API v2 Products"])


def _product_to_schema(p) -> ProductSchema:
    """ORM Product -> ProductSchema (image_url может быть None)."""
    return ProductSchema(
        id=p.id,
        name=p.name,
        brand=p.brand or "",
        price=p.price,
        image_url=p.image_url or "",
        stock=p.stock,
    )


@product_router.get("/products", response_model=ProductListResponse)
async def api_get_products_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Список активных товаров с пагинацией (GET)."""
    product_svc = ProductService(db)
    items, total = await product_svc.get_products_list(page=page, page_size=page_size)
    return ProductListResponse(
        items=[_product_to_schema(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@product_router.get("/products/{product_id}", response_model=ProductSchema)
async def api_get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel | None = Depends(get_current_user_optional),
):
    """Один товар по id (GET)."""
    product_svc = ProductService(db)
    try:
        product = await product_svc.get_product_detail(product_id, current_user)
        return product
    except ProductNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Продукт с id:{product_id} не найден",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения продукта",
        )


@product_router.get("/products/stock/{product_id}", response_model=ProductStockResponse)
async def api_get_product_stock(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Остаток и доступность товара по id (GET)."""
    product_svc = ProductService(db)
    product = await product_svc.crud.get_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Продукт с id:{product_id} не найден",
        )
    return ProductStockResponse(
        product_id=product.id,
        stock=product.stock,
        is_active=product.is_active,
        in_stock=product.stock > 0,
    )


@product_router.put("/products/{product_id}", response_model=ProductSchema)
async def api_update_product(
    product_id: int,
    product: ProductUpdateAPI = Depends(ProductUpdateAPI.as_form),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Обновить товар (PUT). Только seller."""
    product_svc = ProductService(db)
    product_by_id = await product_svc.crud.get_by_id(product_id)
    if not product_by_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Продукт с id:{product_id} не найден",
        )
    await product_svc.update_product_api(
        product_id=product_id,
        data=product,
        category_ids=product.category_ids,
        image=image,
    )
    updated_product = await product_svc.crud.get_by_id_with_categories(product_id)
    return updated_product


@product_router.post(
    "/products",
    response_model=ProductSchema,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_product(
    product: ProductCreateAPI = Depends(ProductCreateAPI.as_form),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_seller),
):
    """Создать товар (POST). Только seller, URL должен быть уникален."""
    product_svc = ProductService(db)
    if product.url:
        product_by_url = await product_svc.crud.get_by_url(product.url)
        if product_by_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Продукт с таким URL-адресом уже существует",
            )
    await product_svc.create_product_api(
        data=product, seller_id=current_user.id, image=image
    )
    created_product = await product_svc.crud.get_by_url(product.url)
    return created_product


@product_router.delete("/products/{product_id}", response_model=dict)
async def api_delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Деактивировать товар (DELETE soft)."""
    product_svc = ProductService(db)
    product = await product_svc.api_inactive_product(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Продукт не найден или не активен",
        )
    return {"message": f"Продукт {product_id} не активен"}


@product_router.delete("/products/{product_id}/hard", response_model=dict)
async def api_hard_delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Удалить товар из БД безвозвратно (DELETE hard)."""
    product_svc = ProductService(db)
    product = await product_svc.crud.get_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Продукт не найден",
        )
    await product_svc.crud.delete(product_id)
    return {"message": f"Продукт {product_id} безвозвратно удален"}


@product_router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_products(
    import_data: ProductImportList,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_import),
    bypass_auth: bool = Query(False),
):
    """Импорт товаров из JSON (POST). Логика создания категорий/товаров в роутере."""
    if bypass_auth:
        result = await db.scalar(select(UserModel).where(UserModel.id == 1))
        if not result:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Админ не найден")
        current_user = result

    created = []
    for product_data in import_data.products:
        result = await db.scalars(
            select(Product).where(Product.url == product_data.url)
        )
        if result.first():
            continue

        image_url = (
            await save_image_from_url(product_data.images)
            if product_data.images and product_data.images.startswith("http")
            else product_data.images
        )

        categories = []
        parent = None
        for cat_name in product_data.category_path[1:]:
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
                    is_active=True,
                )
                db.add(cat)
                await db.flush()
            categories.append(cat)
            parent = cat

        db_product = Product(
            name=product_data.name,
            name_en=product_data.name_en,
            brand=product_data.brand,
            price=product_data.price,
            url=product_data.url,
            image_url=image_url,
            description_left=product_data.description_left,
            description_right=product_data.description_right,
            stock=10,
            seller_id=current_user.id,
            category_id=[cat.id for cat in categories],
            categories=categories,
            mpn=product_data.mpn,
        )
        db.add(db_product)
        created.append(db_product)

    await db.commit()
    return {
        "imported": len(created),
        "skipped": len(import_data.products) - len(created),
    }
