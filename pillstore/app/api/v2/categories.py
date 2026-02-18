from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.schemas.category import CategoriesSchema, CategoryTreeOut
from app.services.category_service import CategoryService

categories_router = APIRouter(prefix="/api/v2", tags=["API v2 Categories"])


@categories_router.get("/categories", response_model=list[CategoryTreeOut])
async def api_get_categories_tree(db: AsyncSession = Depends(get_db)):
    """Дерево категорий (вложенная структура)."""
    category_svc = CategoryService(db)
    return await category_svc.get_category_tree()


@categories_router.get("/categories/flat", response_model=list[CategoriesSchema])
async def api_get_categories_flat(db: AsyncSession = Depends(get_db)):
    """Плоский список активных категорий."""
    category_svc = CategoryService(db)
    return await category_svc.get_categories_flat()


@categories_router.get("/categories/{category_id}", response_model=CategoriesSchema)
async def api_get_category_by_id(
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Получить одну категорию по id."""
    category_svc = CategoryService(db)
    category = await category_svc.get_category_by_id(category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Категория с id:{category_id} не найдена",
        )
    return category


@categories_router.get(
    "/categories/{category_id}/with-children", response_model=CategoryTreeOut
)
async def api_get_category_with_children(
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Категория по id с дочерними (дерево одного узла)."""
    category_svc = CategoryService(db)
    all_cats = await category_svc.api_category_with_children()
    if category_id not in all_cats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Категория с id:{category_id} не найдена",
        )
    return all_cats[category_id]


@categories_router.post(
    "/categories",
    response_model=CategoriesSchema,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_category(
    name: str = Form(..., min_length=1, max_length=255),
    parent_id: int | None = Form(None),
    is_active: bool = Form(True),
    db: AsyncSession = Depends(get_db),
):
    """Создать категорию."""
    category_svc = CategoryService(db)
    return await category_svc.api_create_category_by_name(name, parent_id, is_active)


@categories_router.put("/categories/{category_id}", response_model=CategoriesSchema)
async def api_update_category(
    category_id: int,
    name: str = Form(None, min_length=1, max_length=255),
    parent_id: int = Form(None),
    is_active: bool = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Обновить категорию."""
    category_svc = CategoryService(db)
    return await category_svc.api_update_category_by_id(
        category_id, name, parent_id, is_active
    )


@categories_router.delete("/categories/{category_id}", response_model=dict)
async def api_inactive_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Деактивировать категорию."""
    category_svc = CategoryService(db)
    msg = await category_svc.api_inactive_category_by_id(category_id)
    return {"message": msg}
