from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import User
from app.db_crud.user_crud import CrudUser

from app.core.security import pwd_context


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_crud = CrudUser(session=session, model=User)

    async def checking_seller(self, user: User):
        if user.role != "seller":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Нет прав доступа"
            )

    async def create_admin_user(
        self, email: str, password: str, role: str
    ) -> tuple[str, int] | str:
        if await self.user_crud.check_user_email(email):
            return (
                f"/admin/error-400?title=Email занят&message={email} уже существует&tab=users",
                302,
            )
        hashed_password = pwd_context.hash(password)
        user_dict = {"email": email, "hashed_password": hashed_password, "role": role}
        user = await self.user_crud.create(user_dict)
        return f"Пользователь {user.email} создан"

    async def update_admin_user(
        self, user_id: int, email: str, password: str | None, role: str
    ) -> tuple[str, int] | str:
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            return (
                f"/admin/error-404?title=Пользователь не найден&message=ID {user_id} не найден&tab=users",
                302,
            )

        if email != user.email and await self.user_crud.check_user_email(email):
            return (
                f"/admin/error-400?title=Email занят&message={email} уже существует&tab=users",
                302,
            )

        update_data = {"email": email, "role": role}
        if password:
            update_data["hashed_password"] = pwd_context.hash(password)

        updated_user = await self.user_crud.update(user, update_data)
        return f"Пользователь {updated_user.email} обновлен"

    async def delete_admin_user(self, user_id: int) -> tuple[str, int] | str:
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            return (
                f"/admin/error-404?title=Пользователь не найден&message=ID {user_id} не найден&tab=users",
                302,
            )

        await self.user_crud.delete(user_id)
        return f"Пользователь {user.email} (ID {user.id}) удален"

    async def get_user_for_edit(self, user_id: int) -> tuple[str, int] | User:
        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден"
            )
        return user
