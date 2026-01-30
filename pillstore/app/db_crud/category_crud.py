from sqlalchemy import select

from app.models.categories import Category
from app.db_crud.base import CRUDBase
from app.schemas.category import CategoryRead


class CrudCategory(CRUDBase):
    def __init__(self, session, model) -> None:
        self.model = model
        self.session = session

    async def list_all(self) -> list[CategoryRead]:
        result = await self.session.execute(select(Category))
        categories = result.scalars().all()
        return [CategoryRead.model_validate(cat) for cat in categories]

    async def get_tree_categories(self) -> list[Category]:
        stmt = (
            select(Category.id, Category.name, Category.parent_id, Category.is_active)
            .where(Category.is_active)
            .order_by(Category.id)
        )
        result = await self.session.execute(stmt)
        return result.unique().all()

    async def get_by_ids(self, category_ids: list[int]) -> list[Category]:
        if not category_ids:
            return []
        stmt = select(self.model).where(self.model.id.in_(category_ids))
        result = await self.session.scalars(stmt)
        return list(result.all())
