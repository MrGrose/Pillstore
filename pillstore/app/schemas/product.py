from datetime import datetime
from decimal import Decimal
from fastapi.exceptions import RequestValidationError
from typing import Annotated
from fastapi import Form
from pydantic import BaseModel, Field, ValidationError, ConfigDict


class ProductSchema(BaseModel):
    id: int
    name: str
    brand: str
    price: Decimal
    image_url: str
    stock: int

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Название товара (3-100 символов)",
    )
    name_en: str | None = Field(
        ..., min_length=0, description="Название товара на анг. (3-100 символов)"
    )
    brand: str | None = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Название бренда (1-100 символов)",
    )
    price: Decimal = Field(
        ..., gt=0, description="Цена товара (больше 0)", decimal_places=2
    )
    cost: Decimal = Field(0, ge=0, description="Себестоимость за единицу")
    url: str | None = None
    stock: int = Field(..., ge=0, description="Остаток на складе")
    category_id: list[int] = Field(default_factory=list)
    is_active: bool
    description_left: str | None = None
    description_right: str | None = None
    image_url: str | None = None
    seller_id: int

    @classmethod
    def as_form(
        cls,
        seller_id: Annotated[int, Form(...)],
        name: Annotated[str, Form(...)],
        price: Annotated[Decimal, Form(...)],
        url: Annotated[str | None, Form(...)],
        stock: Annotated[int, Form(...)],
        description_left: Annotated[str, Form(...)],
        description_right: Annotated[str, Form(...)],
        is_active: Annotated[bool, Form(...)],
        image_url: Annotated[str | None, Form(...)],
        brand: Annotated[str | None, Form()] = None,
        category_id: Annotated[int, Form(...)] = None,
        name_en: Annotated[str, Form()] = "",
    ) -> "ProductCreate":
        try:
            return cls(
                name=name,
                name_en=name_en or "",
                brand=brand,
                price=price,
                url=url,
                stock=stock,
                category_id=category_id,
                description_left=description_left,
                description_right=description_right,
                is_active=is_active,
                image_url=image_url,
                seller_id=seller_id,
            )
        except ValidationError as e:
            raise RequestValidationError(e.errors())


class ProductImport(BaseModel):
    name: str
    name_en: str | None = None
    brand: str | None = None
    price: Decimal
    url: str
    images: str | None = None
    stock: int
    mpn: str | None = None
    category_path: list[str]
    description_left: str | None = None
    description_right: str | None = None


class ProductImportList(BaseModel):
    products: list[ProductImport]


class ProductRead(BaseModel):
    id: int
    name: str
    brand: str
    price: float
    image_url: str | None = None
    cart_qty: int = 0
    stock: int = 0

    model_config = ConfigDict(from_attributes=True)


class PageUrls(BaseModel):
    page_urls: dict[int, str]
    prev_url: str
    next_url: str
    first_url: str
    last_url: str

    model_config = ConfigDict(from_attributes=True)


class ProductPagination(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int
    page_urls: PageUrls
    total_pages: int
    page_size_urls: dict[int, str]
    pagination_sizes: list[int]

    model_config = ConfigDict(from_attributes=True)


class ProductUpdate(BaseModel):
    name: str | None = None
    name_en: str = ""
    brand: str = ""
    price: float | None = None
    cost: float | None = None
    stock: int | None = None
    url: str | None = None
    is_active: bool = True
    category_ids: list[int] = []
    description_left: str = ""
    description_right: str = ""
    created_at: datetime | None = None


class ProductStockResponse(BaseModel):
    product_id: int
    stock: int
    is_active: bool
    in_stock: bool

    model_config = ConfigDict(from_attributes=True)


class AdminProductsResponse(BaseModel):
    active_products: list[ProductSchema] = Field(
        default_factory=list, description="Активные товары"
    )
    inactive_products: list[ProductSchema] = Field(
        default_factory=list, description="Неактивные товары"
    )
    total_active: int = Field(..., ge=0)
    total_inactive: int = Field(..., ge=0)


class ProductListResponse(BaseModel):
    items: list[ProductSchema] = Field(default_factory=list)
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)


class AdminProductsPaginatedResponse(BaseModel):
    items: list[ProductSchema] = Field(
        default_factory=list, description="Товары на странице"
    )
    total: int = Field(..., ge=0, description="Всего в выбранной категории")
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_active: int = Field(..., ge=0, description="Всего активных")
    total_inactive: int = Field(..., ge=0, description="Всего неактивных")


class ProductUpdateAPI(BaseModel):
    name: str | None = None
    name_en: str = ""
    brand: str = ""
    price: float | None = None
    stock: int | None = None
    is_active: bool = True
    category_ids: list[int] = []
    description_left: str = ""
    description_right: str = ""
    created_at: datetime | None = None

    @classmethod
    def as_form(  # noqa: C901
        cls,
        name: str | None = Form(None),
        name_en: str = Form(""),
        brand: str = Form(""),
        price: float | None = Form(None),
        stock: int | None = Form(None, ge=0),
        is_active: bool = Form(True),
        category_ids: str = Form(""),
        description_left: str = Form(""),
        description_right: str = Form(""),
        created_at: str | None = Form(None),
    ) -> "ProductUpdateAPI":

        cat_ids = []
        if category_ids:
            cat_ids = [int(id.strip()) for id in category_ids.split(",") if id.strip()]

        created_at_dt = None
        if created_at and created_at not in ["", "string", "null"]:
            try:
                created_at_dt = datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                )
            except ValueError:
                pass
        return cls(
            name=name,
            name_en=name_en,
            brand=brand,
            price=price,
            stock=stock,
            is_active=is_active,
            category_ids=cat_ids,
            description_left=description_left,
            description_right=description_right,
            created_at=created_at_dt,
        )


class ProductCreateAPI(BaseModel):
    name: str
    name_en: str | None = None
    brand: str | None = None
    price: Decimal
    url: str | None = None
    stock: int
    categories: list[str] | list[int] = Field(default_factory=list)
    is_active: bool
    description_left: str | None = None
    description_right: str | None = None
    seller_id: int

    @classmethod
    def as_form(
        cls,
        seller_id: int = Form(..., description="ID продавца"),
        name: str = Form(..., description="Название товара"),
        price: Decimal = Form(..., description="Цена товара"),
        url: str | None = Form(None, description="URL товара (если есть)"),
        stock: int = Form(..., description="Количество на складе"),
        description_left: str = Form(..., description="Описание слева"),
        description_right: str = Form(..., description="Описание справа"),
        is_active: bool = Form(..., description="Активен ли товар"),
        brand: str | None = Form(None, description="Бренд"),
        categories: str = Form(
            "",
            description="Можно передавать 1,2,3 или Продукты питания, Мед, Стевия или пустым",
        ),
        name_en: str = Form("", description="Название на английском"),
    ) -> "ProductCreateAPI":

        raw_items = [item.strip() for item in categories.split(",") if item.strip()]
        category_items = []
        for item in raw_items:
            if item.isdigit():
                category_items.append(int(item))
            else:
                category_items.append(item)
        return cls(
            name=name,
            name_en=name_en,
            brand=brand,
            price=price,
            url=url,
            stock=stock,
            categories=category_items,
            description_left=description_left,
            description_right=description_right,
            is_active=is_active,
            seller_id=seller_id,
        )
