from decimal import Decimal

from app.core.logger import logger
from app.db_crud.cart_crud import CrudCart
from app.db_crud.category_crud import CrudCategory
from app.db_crud.order_crud import CrudOrder
from app.db_crud.products_crud import CrudProduct
from app.exceptions.handlers import ProductNotFoundError
from app.models.cart_items import CartItem
from app.models.categories import Category
from app.models.orders import Order
from app.models.products import Product
from app.models.users import User
from app.schemas.category import CategoryTreeOut
from app.exceptions.handlers import BusinessError
from app.schemas.product import (ProductCreate, ProductCreateAPI,
                                 ProductImportList, ProductPagination,
                                 ProductRead, ProductUpdateAPI)
from app.utils.description_parser import formatted_description
from app.utils.iherb_scraper import IHerbScraper
from app.utils.utils import (remove_product_image, save_image_from_url,
                             save_product_image)
from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudProduct(session=session, model=Product)
        self.cat = CrudCategory(session=session, model=Category)
        self.order_crud = CrudOrder(session=session, model=Order)
        self.scraper = IHerbScraper()

    async def get_products_page(
        self,
        page: int,
        page_size: int,
        search: str | None,
        request: Request,
        category_id: int | None = None,
    ) -> ProductPagination:
        pagination = await self.crud.paginate_products(
            page, page_size, search, request, category_id
        )
        if pagination.items:
            ids = [p.id for p in pagination.items]
            reserved = await self.order_crud.get_pending_reserved_map(ids)
            items_with_available = [
                ProductRead(
                    **p.model_dump(exclude={"available_stock"}),
                    available_stock=(p.stock or 0) - reserved.get(p.id, 0),
                )
                for p in pagination.items
            ]
            return ProductPagination(
                **pagination.model_dump(exclude={"items"}),
                items=items_with_available,
            )
        return pagination

    async def get_product_stock(self, product_id: int) -> int:
        product = await self.crud.get_by_id(product_id)
        return (product.stock or 0) if product else 0

    async def get_product_stock_info(
        self, product_id: int
    ) -> dict:
        product = await self.crud.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        reserved = await self.order_crud.get_pending_reserved(product_id)
        available = (product.stock or 0) - reserved
        return {
            "product_id": product.id,
            "stock": available,
            "is_active": product.is_active,
            "in_stock": available > 0,
        }

    async def get_product_with_categories(self, product_id: int) -> Product | None:
        return await self.crud.get_by_id_with_categories(product_id)

    @staticmethod
    def format_description_for_api(product: Product) -> str | None:
        raw = getattr(product, "description", None)
        if raw is None:
            return None
        if isinstance(raw, dict):
            parts = []
            for title, blocks in raw.items():
                if isinstance(blocks, list):
                    parts.append(title + "\n" + "\n".join(str(b) for b in blocks))
                else:
                    parts.append(str(blocks))
            return "\n\n".join(parts) if parts else None
        return str(raw)

    async def hard_delete_product(self, product_id: int) -> None:
        product = await self.crud.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        await self.crud.delete(product_id)

    async def get_available_products_for_order(self) -> list[Product]:
        return await self.crud.get_available_for_order()

    async def get_product_detail(self, product_id: int, user: User | None) -> Product:
        product = await self.crud.get_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id)
        reserved = await self.order_crud.get_pending_reserved(product_id)
        product.available_stock = (product.stock or 0) - reserved
        if user:
            await self.cart_qty_for_product(product_id, user, product)
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
            logger.error("Импорт iHerb: не удалось распарсить url=%s", url)
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

    async def get_products_list(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[Product], int]:
        return await self.crud.get_products_paginated(
            is_active=True, page=page, page_size=page_size
        )

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

    async def update_product_api(
        self,
        product_id: int,
        data: ProductUpdateAPI,
        category_ids: list[int],
        image: UploadFile | None = None,
    ) -> tuple[str, str]:
        product = await self.crud.get_by_id_with_categories(product_id)
        if not product:
            raise ProductNotFoundError(product_id)

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            if hasattr(product, key) and value is not None:
                setattr(product, key, value)

        if image and image.filename:
            if product.image_url:
                remove_product_image(product.image_url)
            product.image_url = await save_product_image(image)

        if category_ids is not None:
            new_categories = await self.cat.get_by_ids(category_ids)
            product.categories = new_categories

        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)

        return f"Продукт с id:{product.id} {product.name} обновлен", "success"

    async def create_product_api(
        self,
        data: ProductCreateAPI,
        seller_id: int,
        image: UploadFile | None = None,
    ) -> Product:
        if data.url:
            existing = await self.crud.get_by_url(data.url)
            if existing:
                raise BusinessError(
                    "Товар", "Продукт с таким URL-адресом уже существует"
                )

        category_ids = []
        if data.categories:
            if data.categories and all(isinstance(c, int) for c in data.categories):
                category_ids = data.categories
                categories = await self.cat.get_by_ids(category_ids)
                if len(categories) != len(category_ids):
                    existing_ids = [c.id for c in categories]
                    missing = set(category_ids) - set(existing_ids)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Категории с ID {missing} не найдены",
                    )
            else:
                categories = await self.cat.create_category_hierarchy(data.categories)
                category_ids = [cat.id for cat in categories]

        product_dict = data.model_dump(exclude={"categories"})
        product_dict["seller_id"] = seller_id
        product_dict["category_id"] = category_ids
        product = await self.crud.create(product_dict)

        if image and image.filename:
            product.image_url = await save_product_image(image)

        if category_ids:
            categories = await self.cat.get_by_ids(category_ids)
            product.categories = categories
            self.session.add(product)

        await self.session.commit()
        await self.session.refresh(product)

        return product

    async def api_inactive_product(self, product_id: int) -> Product | None:
        product = await self.crud.get_by_id(product_id)
        if not product:
            return None
        await self.crud.inactive_product(product.id)
        return product

    async def import_products_from_list(
        self, import_data: ProductImportList, seller_id: int
    ) -> dict:
        created = []
        for product_data in import_data.products:
            existing = await self.crud.get_by_url(product_data.url)
            if existing:
                continue
            image_url = (
                await save_image_from_url(product_data.images)
                if product_data.images and product_data.images.startswith("http")
                else product_data.images
            )
            categories = []
            parent = None
            for cat_name in product_data.category_path[1:]:
                cat_result = await self.session.scalars(
                    select(Category).where(
                        or_(
                            Category.name == cat_name,
                            Category.name.ilike(f"%{cat_name}%"),
                        )
                    )
                )
                cat = cat_result.first()
                if not cat:
                    cat = Category(
                        name=cat_name,
                        parent_id=parent.id if parent else None,
                        is_active=True,
                    )
                    self.session.add(cat)
                    await self.session.flush()
                categories.append(cat)
                parent = cat
            db_product = Product(
                name=product_data.name,
                name_en=product_data.name_en or "",
                brand=product_data.brand or "",
                price=product_data.price,
                url=product_data.url,
                image_url=image_url,
                description_left=product_data.description_left or "",
                description_right=product_data.description_right or "",
                stock=product_data.stock,
                is_active=product_data.is_active,
                seller_id=seller_id,
                category_id=[c.id for c in categories],
                categories=categories,
                mpn=product_data.mpn,
            )
            self.session.add(db_product)
            created.append(db_product)
        await self.session.commit()
        return {
            "imported": len(created),
            "skipped": len(import_data.products) - len(created),
        }
