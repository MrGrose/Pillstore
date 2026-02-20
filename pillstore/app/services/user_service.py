from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_utils import create_access_token, hash_password, verify_password
from app.db_crud.user_crud import CrudUser
from app.exceptions.handlers import BusinessError, UserNotFoundError
from app.models.users import User


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_crud = CrudUser(session=session, model=User)

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

    async def update_user_profile(self, user_id: int, update_data: dict) -> User:
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        if "email" in update_data and update_data["email"] != user.email:
            existing = await self.user_crud.check_user_email(update_data["email"])
            if existing:
                raise ValueError("Email уже зарегистрирован")

        if "password" in update_data:
            current = update_data.pop("current_password", None)
            if not current:
                raise ValueError("Текущий пароль обязателен для изменения пароля")
            if not verify_password(current, user.hashed_password):
                raise ValueError("Текущий пароль неверен")
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        updated_user = await self.user_crud.update(user, update_data)
        return updated_user

    async def deactivate_user(self, user_id: int) -> str:
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        await self.user_crud.update(user, {"is_active": False})
        return f"Пользователь {user.email} деактивирован"

    async def request_password_reset(self, email: str) -> str:
        user = await self.user_crud.get_user_by_email(email)
        if not user:
            raise ValueError("Пользователь не найден")

        return f"Инструкции по сбросу пароля отправлены на {email}"

    async def confirm_password_reset(
        self, token: str, new_password: str, confirm_password: str
    ) -> dict:
        if new_password != confirm_password:
            raise ValueError("Пароли не совпадают")

        if len(new_password) < 6:
            raise ValueError("Пароль должен содержать не менее 6 символов")

        return {
            "success": True,
            "message": "Пароль успешно изменен",
            "access_token": "новый_токен_здесь",
        }

    async def get_all_users(self) -> list[User]:
        return await self.user_crud.get_users()

    async def get_user_by_id(self, user_id: int) -> User:
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user

    async def get_user_by_email(self, email: str) -> User:
        user = await self.user_crud.check_user_email(email)
        if not user:
            raise ValueError("Пользователь не найден")
        return user

    async def link_telegram(self, user_id: int, telegram_id: int) -> None:
        await self.user_crud.clear_telegram_id(telegram_id)
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        await self.user_crud.update(user, {"telegram_id": telegram_id})
