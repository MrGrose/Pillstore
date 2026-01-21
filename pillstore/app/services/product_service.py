from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request

from app.models.cart_items import CartItem
from app.models.users import User
from app.models.products import Product
from app.models.categories import Category

from app.db_crud.cart_crud import CrudCart
from app.db_crud.products_crud import CrudProduct

from app.schemas.product import ProductPagination
from app.exceptions.products import ProductNotFoundError

from app.models.associations import product_categories
from sqlalchemy.orm import selectinload

class ProductService:
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudProduct(session=session, model=Product)
    
    async def get_products_page(
        self, 
        page: int, 
        page_size: int, 
        search: str | None, 
        request: Request,
        category_id: int | None = None,
    ) -> ProductPagination:
        return await self.crud.pagination_page_products(page, page_size, search, request, category_id)

    async def get_product_detail(self, product_id: int, user: User | None) -> Product:
        product = await self.crud.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        if user:
            await self.cart_qty_for_product(product_id, user, product)
            product.available_stock = product.stock - getattr(product, 'cart_qty', 0)
        else:
            product.available_stock = product.stock
        return product
    
    async def cart_qty_for_product(self, product_id: int, user: User, product: Product) -> None:
        cart_crud = CrudCart(self.session, model=CartItem)
        await cart_crud.cart_qty(user, product_id, product)
        
        
    async def get_categories_tree(self, db: AsyncSession):
        # Корневые категории
        root_categories = (await db.scalars(
            select(Category)
            .where(Category.parent_id.is_(None))
            .order_by(Category.name)
        )).all()
        
        # Функция для всех уровней
        async def load_subs(cat):
            subcats = (await db.scalars(
                select(Category)
                .where(Category.parent_id == cat.id)
                .order_by(Category.name)
            )).all()
            for sub in subcats:
                sub.product_count = await db.scalar(
                    select(func.count(product_categories.c.product_id))
                    .where(product_categories.c.category_id == sub.id)
                )
                # 🔥 РЕКУРСИЯ: загрузи внуков!
                await load_subs(sub)
            cat.subcategories = subcats
        
        # Корни
        for cat in root_categories:
            cat.product_count = await db.scalar(
                select(func.count(product_categories.c.product_id))
                .where(product_categories.c.category_id == cat.id)
            )
            await load_subs(cat)
        
        # Топ-5 (тоже с рекурсией)
        top_categories = (await db.scalars(
            select(Category)
            .join(product_categories)
            .group_by(Category.id)
            .order_by(func.count(product_categories.c.product_id).desc())
            .limit(5)
        )).all()
        
        for cat in top_categories:
            cat.product_count = await db.scalar(
                select(func.count(product_categories.c.product_id))
                .where(product_categories.c.category_id == cat.id)
            )
            await load_subs(cat)
        
        return {"root_categories": root_categories, "top_categories": top_categories}
