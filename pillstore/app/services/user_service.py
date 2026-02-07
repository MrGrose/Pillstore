from sqlalchemy.ext.asyncio import AsyncSession


from app.models.users import User
from app.db_crud.user_crud import CrudUser

from app.core.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
)
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

    async def validate_register_data(self, email: str, password: str) -> dict[str, str]:
        errors = await self._validate_base_data(
            email, password, check_user_exists=False
        )
        if "email" not in errors:
            existing_user = await self.user_crud.check_user_email(email)
            if existing_user:
                errors["email"] = "Пользователь с таким email уже зарегистрирован"

        return errors

    async def validate_login_data(self, email: str, password: str) -> dict[str, str]:
        errors = await self._validate_base_data(email, password, check_user_exists=True)
        if not errors.get("password") and "email" not in errors:
            user = await self.user_crud.get_user_by_email(email)
            if not verify_password(password, user.hashed_password):
                errors["password"] = "Неверный пароль"

        return errors

    async def _validate_base_data(
        self, email: str, password: str, check_user_exists: bool = False
    ) -> dict[str, str]:
        errors = {}

        if not self._is_valid_email(email):
            errors["email"] = "Введите корректный email"
        elif check_user_exists:
            user = await self.user_crud.get_user_by_email(email)
            if not user:
                errors["email"] = "Пользователь с таким email не найден"

        if not self._is_valid_password(password):
            errors["password"] = "Пароль должен содержать не менее 6 символов"

        return errors

    def _is_valid_email(self, email: str) -> bool:
        if not email or "@" not in email:
            return False
        valid_domains = (".com", ".ru", ".yandex", ".org", ".net", ".gmail", ".ya")
        return any(email.endswith(domain) for domain in valid_domains)

    def _is_valid_password(self, password: str) -> bool:
        return bool(password and len(password) >= 6)

    async def reset_password(
        self, email: str, new_password: str, confirm_password: str
    ) -> dict:
        validation_errors = await self._validate_base_data(
            email, new_password, check_user_exists=True
        )

        if new_password != confirm_password:
            if "password" not in validation_errors:
                validation_errors["password"] = "Пароли не совпадают"

        if validation_errors:
            return {"success": False, "errors": validation_errors}

        user = await self.user_crud.get_user_by_email(email)

        hashed_password = hash_password(new_password)
        await self.user_crud.update(user, {"hashed_password": hashed_password})

        access_token = create_access_token(
            {"sub": user.email, "role": user.role, "id": user.id}
        )

        return {
            "success": True,
            "message": "Пароль успешно изменен",
            "access_token": access_token,
            "user": user,
        }
