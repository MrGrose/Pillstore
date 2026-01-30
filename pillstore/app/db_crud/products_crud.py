from sqlalchemy import and_, select, func, or_, Select
from sqlalchemy.orm import selectinload

from app.db_crud.base import CRUDBase
from app.schemas.product import ProductPagination, PageUrls, ProductUpdate
from fastapi import HTTPException, Request, status

from app.core.config import PAGINATION_SIZES
from app.models.products import Product
from app.models.orders import OrderItem


class CrudProduct(CRUDBase):
    def __init__(self, session, model) -> None:
        self.model = model
        self.session = session

    async def pagination_page_products(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        request: Request | None = None,
        category_id: int | None = None,
    ) -> ProductPagination:
        base_query = await self.search_products(search, category_id)
        products_stmt = base_query.offset((page - 1) * page_size).limit(page_size)
        items = (await self.session.scalars(products_stmt)).all()
        total_stmt = select(func.count()).select_from(base_query.subquery())
        total = await self.session.scalar(total_stmt)

        total_pages = (total + page_size - 1) // page_size

        page_urls = await self.generate_page_urls(
            page_size, request, total_pages, page, search, category_id
        )
        page_size_urls = await self.generate_page_size_urls(
            request, search, category_id
        )

        return ProductPagination(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            page_urls=page_urls,
            page_size_urls=page_size_urls,
            pagination_sizes=PAGINATION_SIZES,
        )

    async def generate_page_urls(
        self,
        page_size: int,
        request: Request | None,
        total_pages: int,
        page: int,
        search: str | None = None,
        category_id: int | None = None,
    ) -> PageUrls:
        page_urls = {}
        prev_url = next_url = first_url = last_url = ""

        if request and total_pages > 0:
            for pag in range(1, total_pages + 1):
                params = {"page": pag, "page_size": page_size}
                if search:
                    params["search_product"] = search
                if category_id:
                    params["category_id"] = category_id
                url = request.url.replace_query_params(**params)
                page_urls[pag] = str(url)

            first_url = page_urls.get(1, "")
            last_url = page_urls.get(total_pages, "")
            prev_url = page_urls.get(page - 1, first_url) if page > 1 else ""
            next_url = page_urls.get(page + 1, last_url) if page < total_pages else ""

        return PageUrls(
            page_urls=page_urls,
            prev_url=prev_url,
            next_url=next_url,
            first_url=first_url,
            last_url=last_url,
        )

    async def generate_page_size_urls(
        self,
        request: Request | None,
        search: str | None = None,
        category_id: int | None = None,
    ) -> dict[int, str]:
        page_size_urls: dict[int, str] = {}
        if request:
            for size in PAGINATION_SIZES:
                params = {"page": 1, "page_size": size}
                if search:
                    params["search_product"] = search
                if category_id:
                    params["category_id"] = category_id
                page_size_urls[size] = str(request.url.replace_query_params(**params))
        return page_size_urls

    async def search_products(
        self, search: str | None = None, category_id: int | None = None
    ) -> Select:
        stmt = (
            select(self.model)
            .where(self.model.is_active.is_(True))
            .where(self.model.stock > 0)
        )

        if category_id:
            stmt = stmt.where(self.model.category_id.any(category_id))

        if search:
            search_value = search.strip()
            if search_value:
                ts_query_en = func.websearch_to_tsquery("english", search_value)
                ts_query_ru = func.websearch_to_tsquery("russian", search_value)

                ts_match_any = or_(
                    self.model.tsv.op("@@")(ts_query_en),
                    self.model.tsv.op("@@")(ts_query_ru),
                )
                stmt = stmt.where(ts_match_any)

                rank_col = func.greatest(
                    func.ts_rank_cd(self.model.tsv, ts_query_en),
                    func.ts_rank_cd(self.model.tsv, ts_query_ru),
                ).label("rank")
                stmt = stmt.order_by(rank_col.desc())
            else:
                stmt = stmt.order_by(self.model.id.asc())
        else:
            stmt = stmt.order_by(self.model.id.asc())

        return stmt

    async def get_product_active(self, product_id: int) -> Product:
        product_db = select(self.model).where(
            and_(self.model.id == product_id, self.model.is_active.is_(True))
        )
        product = await self.session.scalar(product_db)
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Товар не найден")

        return product

    async def get_product_available(self, product_id: int, quantity: int) -> Product:
        return await self.session.scalar(
            select(self.model).where(
                self.model.id == product_id, self.model.stock >= quantity
            )
        )

    async def count_order_items(self, product_id: int) -> int:
        result = await self.session.scalar(
            select(func.count())
            .select_from(OrderItem)
            .where(OrderItem.product_id == product_id)
        )
        return result or 0

    async def get_by_id_with_categories(self, id: int) -> Product:
        stmt = (
            select(self.model)
            .options(selectinload(self.model.categories))
            .where(self.model.id == id)
        )
        result = await self.session.scalars(stmt)
        return result.first()

    async def update_product(self, product_id: int, data: ProductUpdate) -> Product:
        product_with_categories = await self.get_by_id_with_categories(product_id)
        product = await self.update(
            product_with_categories, data.model_dump(exclude={"image_url"})
        )
        return product
