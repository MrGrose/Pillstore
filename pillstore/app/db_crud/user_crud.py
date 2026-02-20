from sqlalchemy import select

from app.db_crud.base import CRUDBase
from app.models.users import User


class CrudUser(CRUDBase):
    def __init__(self, session, model) -> None:
        self.model = model
        self.session = session

    async def get_user(self, user: User) -> User:
        return await self.get_by_id(user.id)

    async def get_users(self) -> list[User]:
        db_users = await self.session.scalars(select(self.model))
        users = list(db_users.all())
        return users

    async def check_user_email(self, email: str) -> User:
        db_user = await self.session.scalar(
            select(self.model).where(self.model.email == email)
        )
        return db_user

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.scalars(
            select(self.model).where(
                self.model.email == email, self.model.is_active.is_(True)
            )
        )
        return result.first()

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.scalars(
            select(self.model).where(
                self.model.telegram_id == telegram_id,
                self.model.is_active.is_(True),
            )
        )
        return result.first()

    async def clear_telegram_id(self, telegram_id: int) -> None:
        from sqlalchemy import update
        await self.session.execute(
            update(self.model).where(self.model.telegram_id == telegram_id).values(telegram_id=None)
        )
        await self.session.commit()
