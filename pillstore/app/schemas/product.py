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
    name: str
    name_en: str = ""
    brand: str = ""
    price: float
    stock: int
    is_active: bool = True
    category_ids: list[int] = []
    description_left: str = ""
    description_right: str = ""
    created_at: datetime | None
    expiry_at: datetime | None
