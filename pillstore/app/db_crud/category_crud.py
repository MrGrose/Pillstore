from sqlalchemy import or_, select

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

    async def create_category_hierarchy(
        self, category_path: list[str]
    ) -> list[Category]:
        categories = []
        parent = None
        for cat_name in category_path[1:]:
            cat_name = cat_name.strip()
            if cat_name and len(cat_name) > 1:
                cat_result = await self.session.scalars(
                    select(self.model)
                    .where(
                        or_(
                            self.model.name == cat_name,
                            self.model.name.ilike(f"%{cat_name}%"),
                        )
                    )
                    .where(self.model.parent_id == (parent.id if parent else None))
                )
                cat = cat_result.first()
                if not cat:
                    cat = self.model(
                        name=cat_name,
                        parent_id=parent.id if parent else None,
                        is_active=True,
                    )
                    self.session.add(cat)

                categories.append(cat)
                parent = cat

        await self.session.flush()
        return categories
