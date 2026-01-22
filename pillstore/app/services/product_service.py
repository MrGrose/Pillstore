from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart_items import CartItem
from app.models.users import User
from app.models.products import Product
from app.models.categories import Category

from app.db_crud.cart_crud import CrudCart
from app.db_crud.products_crud import CrudProduct
from app.db_crud.category_crud import CrudCategory

from app.schemas.product import ProductPagination
from app.exceptions.products import ProductNotFoundError

from app.schemas.category import CategoryTreeOut

from app.services.utils import formatted_description

class ProductService:
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudProduct(session=session, model=Product)
        self.cat = CrudCategory(session=session, model=Category)
    
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
            product.available_stock = product.stock - getattr(product, "cart_qty", 0)
        else:
            product.available_stock = product.stock
        product.description = await formatted_description(product)
        return product
    
    async def cart_qty_for_product(self, product_id: int, user: User, product: Product) -> None:
        cart_crud = CrudCart(self.session, model=CartItem)
        await cart_crud.cart_qty(user, product_id, product)
        
    async def get_flat_tree(self) -> list[dict]:
        categories = await self.cat.get_tree_categories()
        all_cats: dict[int, CategoryTreeOut] = {
            cat.id: CategoryTreeOut.model_validate(cat)
            for cat in categories
        }
        for cat_id, cat in all_cats.items():
            if cat.parent_id and cat.parent_id in all_cats:
                parent = all_cats[cat.parent_id]
                cat.level = parent.level + 1
                cat.path = parent.path + [cat_id]
                parent.children.append(cat)
        
        roots = [cat for cat in all_cats.values() if cat.parent_id is None]
        
        def flatten(node: CategoryTreeOut, result: list[dict]):
            result.append(node.model_dump(mode="json"))
            for child in node.children:
                flatten(child, result)
        
        flat_tree = []
        for root in roots:
            flatten(root, flat_tree)
        
        return flat_tree