from fastapi.security import OAuth2PasswordBearer
import jwt
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import User as UserModel
from app.core.config import SECRET_KEY, ALGORITHM
from app.core.deps import get_db
from app.exceptions.handlers import (
    AuthException,
    TokenExpiredError,
    InvalidCredentialsError,
)
from app.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/token")


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserModel | None:
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
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    payload = decode_token(token)
    user_svc = UserService(db)
    user = await user_svc.user_crud.get_user_by_email(payload["sub"])

    if user is None:
        raise InvalidCredentialsError()

    return user
