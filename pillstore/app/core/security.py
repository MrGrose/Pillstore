import json
import hmac
import hashlib
from urllib.parse import unquote

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.core.mini_app_token import get_telegram_id_by_mini_token
from app.exceptions.handlers import (
    AuthException,
    InvalidCredentialsError,
    TokenExpiredError,
)
from app.models.users import User as UserModel
from app.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/token")
oauth2_scheme_swagger = OAuth2PasswordBearer(
    tokenUrl="/api/v2/token", auto_error=False
)


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    if not init_data or not bot_token:
        return None
    parsed = {}
    received_hash = ""
    for part in init_data.split("&"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        if k == "hash":
            received_hash = v
            continue
        parsed[k] = unquote(v)
    if not received_hash:
        return None
    data_check = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
    secret = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    expected = hmac.new(
        secret, data_check.encode(), hashlib.sha256
    ).hexdigest()
    if expected != received_hash:
        return None
    return parsed


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str | None = payload.get("sub")
        if email is None:
            raise InvalidCredentialsError()
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.PyJWTError:
        raise InvalidCredentialsError()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    user_svc = UserService(db)
    payload = decode_token(token)
    user = await user_svc.user_crud.get_user_by_email(payload["sub"])

    if user is None:
        raise InvalidCredentialsError()

    return user


async def get_current_seller(
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    if current_user.role != "seller":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только у продавцов есть права доступа",
        )
    return current_user


def _get_telegram_id_from_request(request: Request) -> int | None:
    init_data = request.headers.get("X-Telegram-Init-Data")
    if init_data and settings.TELEGRAM_BOT_TOKEN:
        data = validate_telegram_init_data(init_data, settings.TELEGRAM_BOT_TOKEN)
        if data:
            user_json = data.get("user")
            if user_json:
                try:
                    user_obj = json.loads(user_json)
                    return int(user_obj.get("id"))
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
    mini_token = request.headers.get("X-Mini-App-Token")
    if mini_token:
        tid = get_telegram_id_by_mini_token(mini_token.strip())
        if tid is not None:
            return tid
    tid = request.headers.get("X-Telegram-User-Id")
    if tid:
        try:
            return int(tid)
        except ValueError:
            pass
    return None


async def get_current_user_any(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    telegram_id = _get_telegram_id_from_request(request)
    if telegram_id is not None:
        user_svc = UserService(db)
        user = await user_svc.user_crud.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Telegram не привязан к пользователю. Введите email в боте.",
            )
        return user
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    user_svc = UserService(db)
    payload = decode_token(token)
    user = await user_svc.user_crud.get_user_by_email(payload["sub"])
    if user is None:
        raise InvalidCredentialsError()
    return user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserModel | None:
    telegram_id = _get_telegram_id_from_request(request)
    if telegram_id is not None:
        user_svc = UserService(db)
        return await user_svc.user_crud.get_user_by_telegram_id(telegram_id)
    user_svc = UserService(db)
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        return await user_svc.user_crud.get_user_by_email(payload["sub"])
    except AuthException:
        return None


async def get_current_user_import(
    token: str = Depends(oauth2_scheme_swagger),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
        user_svc = UserService(db)
        user = await user_svc.user_crud.get_user_by_email(payload["sub"])

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия токена истек",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
