from app.core.deps import get_db
from app.core.security import (get_current_seller, get_current_user_import,
                               get_current_user_optional)
from app.exceptions.handlers import BusinessError, ProductNotFoundError
from app.models.users import User as UserModel
from app.schemas.product import (ProductCreateAPI, ProductDetailSchema,
                                 ProductImportList, ProductListResponse,
                                 ProductSchema, product_to_schema,
                                 ProductStockResponse, ProductUpdateAPI)
from app.services.product_service import ProductService
from fastapi import (APIRouter, Depends, File, HTTPException, Query, UploadFile,
                     status)
from sqlalchemy.ext.asyncio import AsyncSession

product_router = APIRouter(prefix="/api/v2", tags=["API v2 Products"])


@product_router.get("/products", response_model=ProductListResponse)
async def api_get_products_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Список активных товаров с пагинацией."""
    product_svc = ProductService(db)
    items, total = await product_svc.get_products_list(page=page, page_size=page_size)
    return ProductListResponse(
        items=[product_to_schema(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@product_router.get("/products/{product_id}", response_model=ProductDetailSchema)
async def api_get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel | None = Depends(get_current_user_optional),
):
    """Получить один товар по id (с описанием)."""
    product_svc = ProductService(db)
    try:
        product = await product_svc.get_product_detail(product_id, current_user)
        description = ProductService.format_description_for_api(product)
        return ProductDetailSchema(
            id=product.id,
            name=product.name,
            brand=product.brand or "",
            price=product.price,
            image_url=product.image_url or "",
            stock=product.stock,
            description=description,
        )
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
    """Остаток и доступность товара по id (с учётом резерва в pending заказах)."""
    product_svc = ProductService(db)
    try:
        info = await product_svc.get_product_stock_info(product_id)
        return ProductStockResponse(**info)
    except ProductNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Продукт с id:{product_id} не найден",
        )


@product_router.put("/products/{product_id}", response_model=ProductSchema)
async def api_update_product(
    product_id: int,
    product: ProductUpdateAPI = Depends(ProductUpdateAPI.as_form),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Обновить товар (только для продавца)."""
    product_svc = ProductService(db)
    try:
        await product_svc.update_product_api(
            product_id=product_id,
            data=product,
            category_ids=product.category_ids,
            image=image,
        )
        updated_product = await product_svc.get_product_with_categories(product_id)
        return updated_product
    except ProductNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Продукт с id:{product_id} не найден",
        )


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
    """Создать товар (только для продавца, URL должен быть уникален)."""
    product_svc = ProductService(db)
    try:
        created_product = await product_svc.create_product_api(
            data=product, seller_id=current_user.id, image=image
        )
        return created_product
    except BusinessError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@product_router.delete("/products/{product_id}", response_model=dict)
async def api_delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Мягкое удаление товара (деактивация)."""
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
    """Жёсткое удаление товара из БД безвозвратно."""
    product_svc = ProductService(db)
    try:
        await product_svc.hard_delete_product(product_id)
        return {"message": f"Продукт {product_id} безвозвратно удален"}
    except ProductNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Продукт не найден",
        )


@product_router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_products(
    import_data: ProductImportList,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_import),
):
    """Импорт товаров из JSON (только для авторизованного пользователя)."""
    product_svc = ProductService(db)
    return await product_svc.import_products_from_list(
        import_data, current_user.id
    )
