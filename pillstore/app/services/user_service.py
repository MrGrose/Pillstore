from sqlalchemy.ext.asyncio import AsyncSession


from app.models.users import User
from app.db_crud.user_crud import CrudUser

from app.core.security import verify_password, create_access_token, hash_password
from app.exceptions.handlers import (
    UserNotFoundError,
    BusinessError,
)


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_crud = CrudUser(session=session, model=User)

    async def checking_seller(self, user: User):
        if user.role != "seller":
            raise BusinessError("Пользователь", "Нет прав доступа")

    async def create_admin_user(
        self, email: str, password: str, role: str
    ) -> tuple[str, int] | str:
        if await self.user_crud.check_user_email(email):
            raise BusinessError("Пользователь", f"{email} уже существует")
        hashed_password = hash_password(password)
        user_dict = {"email": email, "hashed_password": hashed_password, "role": role}
        user = await self.user_crud.create(user_dict)
        return f"Пользователь {user.email} создан"

    async def update_admin_user(
        self, user_id: int, email: str, password: str | None, role: str
    ) -> tuple[str, int] | str:
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        if email != user.email and await self.user_crud.check_user_email(email):
            raise BusinessError("Пользователь", f"{email} уже существует")

        update_data = {"email": email, "role": role}
        if password:
            update_data["hashed_password"] = hash_password(password)

        updated_user = await self.user_crud.update(user, update_data)
        return f"Пользователь {updated_user.email} обновлен"

    async def delete_admin_user(self, user_id: int) -> tuple[str, int] | str:
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        await self.user_crud.delete(user_id)
        return f"Пользователь {user.email} (ID {user_id}) удален"

    async def get_user_for_edit(self, user_id: int) -> tuple[str, int] | User:
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user

    async def authenticate_user(self, email: str, password: str) -> str:
        user = await self.user_crud.check_user_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise BusinessError("Авторизация", "Неверный email или пароль")
        return create_access_token(
            {"sub": user.email, "role": user.role, "id": user.id}
        )

    async def register_user(self, email: str, password: str, role: str) -> User:
        hashed_pw = hash_password(password)
        user_email = await self.user_crud.check_user_email(email)
        if user_email:
            raise BusinessError("Пользователь", f"{email} уже зарегистрирован")
        user_dict = {"email": email, "hashed_password": hashed_pw, "role": role}
        user = await self.user_crud.create(user_dict)
        return user

    async def validate_registration_data(self, email: str, password: str) -> list[str]:
        errors: list[str] = []
        if "@" not in email or not email.endswith((".com", ".ru", ".de")):
            errors.append("Некорректный email")
        if len(password) < 6:
            errors.append("Пароль не короче 6 символов")

        return errors if errors else []
