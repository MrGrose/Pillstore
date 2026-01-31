from decimal import Decimal
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart_items import CartItem
from app.models.users import User
from app.models.products import Product
from app.models.categories import Category

from app.db_crud.cart_crud import CrudCart
from app.db_crud.products_crud import CrudProduct
from app.db_crud.category_crud import CrudCategory

from app.schemas.product import ProductCreate, ProductPagination
from app.schemas.category import CategoryTreeOut

from app.exceptions.products import ProductNotFoundError

from app.services.utils import formatted_description, save_image_from_url
from app.services.iherb_scraper import IHerbScraper


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudProduct(session=session, model=Product)
        self.cat = CrudCategory(session=session, model=Category)
        self.scraper = IHerbScraper()

    async def get_products_page(
        self,
        page: int,
        page_size: int,
        search: str | None,
        request: Request,
        category_id: int | None = None,
    ) -> ProductPagination:
        return await self.crud.paginate_products(
            page, page_size, search, request, category_id
        )

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

    async def cart_qty_for_product(
        self, product_id: int, user: User, product: Product
    ) -> None:
        cart_crud = CrudCart(self.session, model=CartItem)
        await cart_crud.cart_qty(user, product_id, product)

    async def get_flat_tree(self) -> list[dict]:
        categories = await self.cat.get_tree_categories()
        all_cats: dict[int, CategoryTreeOut] = {
            cat.id: CategoryTreeOut.model_validate(cat) for cat in categories
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

    async def import_iherb_product(self, url: str, seller: User) -> tuple[str, str]:
        scraper = IHerbScraper()
        product_data = scraper.parse_product_page(url)
        if not product_data:
            return "Не удалось распарсить", "error"

        product_create = ProductCreate(
            name=product_data.name or "",
            name_en=product_data.name_en or "",
            brand=product_data.brand or "",
            price=Decimal(str(round(product_data.price or 0.01, 2))),
            url=product_data.url or "",
            stock=product_data.stock or 0,
            is_active=False,
            seller_id=seller.id,
            description_left=product_data.description_left or "",
            description_right=product_data.description_right or "",
            image_url=None,
            category_id=[],
        )

        existing = await self.crud.get_by_url(product_create.url)
        if existing:
            return f"Товар {product_create.name} уже существует", "warning"

        categories = await self.cat.create_category_hierarchy(
            product_data.category_path
        )
        product_create.category_id = [cat.id for cat in categories]

        if product_data.images:
            img_urls = (
                product_data.images
                if isinstance(product_data.images, list)
                else [product_data.images]
            )
            product_create.image_url = await save_image_from_url(img_urls[0])

        product_dict = product_create.model_dump(exclude={"seller_id"})
        product_dict["seller_id"] = seller.id
        product_dict["categories"] = categories

        db_product = Product(**product_dict)
        self.session.add(db_product)
        await self.session.commit()

        return f"ID {db_product.id} {product_create.name} импортирован", "success"

    async def get_products_page_active(
        self,
        page_active: int,
        page_size_active: int,
        search: str | None,
        request: Request,
        category_id: int | None = None,
    ) -> ProductPagination:
        return await self.crud.paginate_products(
            page_active,
            page_size_active,
            search,
            request,
            category_id,
            is_active=True,
            tab_prefix="page_active",
        )

    async def get_products_page_inactive(
        self,
        page_inactive: int,
        page_size_inactive: int,
        search: str | None,
        request: Request,
        category_id: int | None = None,
    ) -> ProductPagination:
        return await self.crud.paginate_products(
            page_inactive,
            page_size_inactive,
            search,
            request,
            category_id,
            is_active=False,
            tab_prefix="page_inactive",
        )
