from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr = Field(description="Email пользователя")
    password: str = Field(min_length=8, description="Пароль (минимум 8 символов)")
    role: str = Field(
        default="buyer",
        pattern="^(seller|buyer)$",
        description="Роль: 'seller или buyer'",
    )


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    role: str
    model_config = ConfigDict(from_attributes=True)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT токен")
    token_type: str = Field(default="bearer", description="Тип токена")


class MessageResponse(BaseModel):
    message: str = Field(..., description="Сообщение")


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, description="Новый пароль")
    current_password: str | None = Field(
        None, description="Текущий пароль для подтверждения"
    )

    model_config = ConfigDict(from_attributes=True)


class ProfileOrderSummary(BaseModel):
    id: int = Field(..., description="ID заказа")
    total_amount: Decimal = Field(..., ge=0, description="Общая стоимость")
    status: str = Field(..., description="Статус заказа")
    created_at: datetime = Field(..., description="Дата создания")

    model_config = ConfigDict(from_attributes=True)


class ProfileResponse(BaseModel):
    user: UserResponse = Field(..., description="Информация о пользователе")
    orders: list[ProfileOrderSummary] = Field(
        default_factory=list, description="Список заказов пользователя"
    )

    model_config = ConfigDict(from_attributes=True)


class LinkTelegramBody(BaseModel):
    email: str = Field(..., description="Email пользователя")
    telegram_id: int = Field(..., description="ID пользователя в Telegram")


class MiniAppTokenResponse(BaseModel):
    token: str = Field(..., description="Токен для ссылки Mini App")
    expires_in: int = Field(..., description="Срок действия в секундах")
