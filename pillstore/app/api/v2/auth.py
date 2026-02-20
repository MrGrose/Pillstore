from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.mini_app_token import MINI_TOKEN_EXPIRY_SEC, create_mini_token
from app.core.security import get_current_user, get_current_user_any
from app.exceptions.handlers import BusinessError
from app.models.users import User as UserModel
from app.schemas.auth import (
    LinkTelegramBody,
    MessageResponse,
    MiniAppTokenResponse,
    TokenResponse,
    UserCreate,
    UserUpdateRequest,
    UserResponse,
)
from app.services.user_service import UserService

auth_router = APIRouter(prefix="/api/v2", tags=["API v2 Auth"])


@auth_router.get("/auth/check-email")
async def check_email(
    email: str = Query(..., description="Email для проверки"),
    db: AsyncSession = Depends(get_db),
):
    """Проверка наличия пользователя по email (для бота)."""
    user_svc = UserService(db)
    user = await user_svc.user_crud.get_user_by_email(email.strip())
    return {"exists": user is not None}


@auth_router.post("/auth/link-telegram", response_model=MessageResponse)
async def link_telegram(
    body: LinkTelegramBody,
    db: AsyncSession = Depends(get_db),
):
    """Привязать Telegram к пользователю по email (для бота после проверки email)."""
    user_svc = UserService(db)
    user = await user_svc.user_crud.get_user_by_email(body.email.strip())
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    await user_svc.link_telegram(user.id, body.telegram_id)
    return MessageResponse(message="Telegram привязан")


@auth_router.post("/auth/mini-app-token", response_model=MiniAppTokenResponse)
async def create_mini_app_token(
    current_user: UserModel = Depends(get_current_user_any),
):
    """Выдать одноразовый токен для входа в Mini App по ссылке (бот передаёт X-Telegram-User-Id)."""
    telegram_id = current_user.telegram_id
    if telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У пользователя не привязан Telegram",
        )
    token = create_mini_token(int(telegram_id))
    return MiniAppTokenResponse(token=token, expires_in=MINI_TOKEN_EXPIRY_SEC)


@auth_router.get("/users/me", response_model=UserResponse)
async def get_current_user_endpoint(
    current_user: UserModel = Depends(get_current_user_any),
):
    """Текущий пользователь (JWT или X-Telegram-User-Id для бота)."""
    return current_user


@auth_router.put("/users/me", response_model=UserResponse)
async def update_current_user(
    update_data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Обновить профиль (проверка текущего пароля в сервисе)."""
    user_service = UserService(db)
    data = update_data.model_dump(exclude_unset=True)
    try:
        updated = await user_service.update_user_profile(current_user.id, data)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@auth_router.delete("/users/me", response_model=MessageResponse)
async def delete_current_user(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Деактивировать текущего пользователя."""
    user_service = UserService(db)
    try:
        msg = await user_service.deactivate_user(current_user.id)
        return MessageResponse(message=msg)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@auth_router.post("/auth/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Регистрация."""
    user_service = UserService(db)
    try:
        user = await user_service.register_user(
            email=user_data.email,
            password=user_data.password,
            role=user_data.role,
        )
        return user
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@auth_router.post("/auth/login", response_model=TokenResponse)
async def login_user(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Вход (возвращает токен доступа)."""
    user_service = UserService(db)
    try:
        token = await user_service.authenticate_user(email=email, password=password)
        return TokenResponse(access_token=token, token_type="bearer")
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@auth_router.post("/token", response_model=TokenResponse)
async def token_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Выдача JWT по email и паролю (форма OAuth2 для кнопки «Authorize» в Swagger)."""
    user_service = UserService(db)
    try:
        access_token = await user_service.authenticate_user(
            email=form_data.username, password=form_data.password
        )
        return TokenResponse(access_token=access_token, token_type="bearer")
    except BusinessError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


@auth_router.post("/auth/logout", response_model=MessageResponse)
async def logout_user(
    current_user: UserModel = Depends(get_current_user),
):
    """Выход (клиент удаляет токен)."""
    return MessageResponse(message="Successfully logged out")


@auth_router.post("/auth/reset-password/request", response_model=MessageResponse)
async def request_password_reset(
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Запрос сброса пароля."""
    user_service = UserService(db)
    try:
        msg = await user_service.request_password_reset(email)
        return MessageResponse(message=msg)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@auth_router.post("/auth/reset-password/confirm")
async def confirm_password_reset(
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Подтверждение сброса пароля."""
    user_service = UserService(db)
    try:
        result = await user_service.confirm_password_reset(
            token=token,
            new_password=new_password,
            confirm_password=confirm_password,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
