from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.category import CategoryRead
from app.db_crud.category_crud import CrudCategory


from app.models.categories import Category


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudCategory(session=session, model=Category)

    async def get_all_categories(self) -> list[CategoryRead]:
        return list(await self.crud.list_all())
