from decimal import Decimal
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import ProductSchema


class CartItemApi(BaseModel):
    id: int = Field(..., description="ID позиции корзины")
    quantity: int = Field(..., ge=1, description="Количество товара")
    product: ProductSchema = Field(..., description="Информация о товаре")

    model_config = ConfigDict(from_attributes=True)


class CartApi(BaseModel):
    user_id: int = Field(..., description="ID пользователя")
    items: List[CartItemApi] = Field(
        default_factory=list, description="Содержимое корзины"
    )
    total_quantity: int = Field(..., ge=0, description="Общее количество товаров")
    total_price: Decimal = Field(..., ge=0, description="Общая стоимость товаров")

    model_config = ConfigDict(from_attributes=True)


class CartItemCreate(BaseModel):
    product_id: int = Field(..., description="ID товара")
    quantity: int = Field(ge=1, description="Количество товара")


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1, description="Новое количество товара")


class CartActionResponse(BaseModel):
    message: str = Field(..., description="Сообщение")
    cart_count: int = Field(
        ..., ge=0, description="Текущее количество единиц товаров в корзине"
    )
    item: dict | None = Field(None, description="Обновлённая позиция (add/update)")
    cart_qty: int | None = Field(None, description="Количество по позиции (при add)")


class CartCountResponse(BaseModel):
    count: int = Field(..., ge=0, description="Количество единиц в корзине")
