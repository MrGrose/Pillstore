from decimal import Decimal
from fastapi.exceptions import RequestValidationError
from typing import Annotated, Any
from fastapi import Form
from pydantic import BaseModel, Field, ValidationError, ConfigDict, field_validator
# from app.core.config import CATEGORIES


# def validate_category_id(cls, v: Any) -> int:
#     if not isinstance(v, int) or v not in CATEGORIES:
#         raise ValueError(f"ID {v} неверный. Допустимые: {list(CATEGORIES.keys())}")
#     return v


class ProductSchema(BaseModel):
    id: int
    name: str
    brand: str
    price: Decimal
    image_url: str
    stock: int
    
    model_config = ConfigDict(from_attributes=True)



class ProductCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, description="Название товара (3-100 символов)")
    brand: str | None = Field(..., min_length=1, max_length=100, description="Название бренда (1-100 символов)")
    price: Decimal = Field(..., gt=0, description="Цена товара (больше 0)", decimal_places=2)
    url: str | None
    stock: int = Field(..., ge=0, description="Остаток на складе")
    category_id: int = Field(..., gt=0)  
    
    # @field_validator("category_id")
    # @classmethod
    # def check_category_id(cls, v: Any) -> int:
    #     if v not in CATEGORIES:
    #         raise ValueError(f"Категория ID={v} не существует. Выберите: {list(CATEGORIES)}")
    #     return v
    
    @classmethod
    def as_form(
            cls,
            name: Annotated[str, Form(...)],
            price: Annotated[Decimal, Form(...)],
            url: Annotated[str | None, Form(...)],
            stock: Annotated[int, Form(...)],
            brand: Annotated[str | None, Form()] = None,
            category_id: Annotated[int, Form(...)] = None,
    ) -> "ProductCreate":
        try:
            return cls(
                name=name,
                brand=brand,
                price=price,
                url=url,
                stock=stock,
                category_id=category_id,
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
    
    
