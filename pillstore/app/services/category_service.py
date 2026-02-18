from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud.category_crud import CrudCategory
from app.models.categories import Category
from app.schemas.category import CategoryRead, CategoryTreeOut


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudCategory(session=session, model=Category)

    async def get_all_categories(self) -> list[CategoryRead]:
        return list(await self.crud.list_all())

    async def get_categories_flat(self):
        return await self.crud.get_all(True)

    async def get_category_by_id(self, category_id: int):
        return await self.crud.get_by_id(category_id)

    async def get_category_tree(self) -> list[dict]:
        categories = await self.crud.get_tree_categories()
        all_cats: dict[int, CategoryTreeOut] = {
            cat.id: CategoryTreeOut.model_validate(cat) for cat in categories
        }
        for cat_id, cat in all_cats.items():
            if cat.parent_id and cat.parent_id in all_cats:
                parent = all_cats[cat.parent_id]
                cat.level = parent.level + 1
                cat.path = parent.path + [cat_id]
                parent.children.append(cat)

        roots = [cat for cat in all_cats.values() if cat.parent_id is None]

        def flatten(node: CategoryTreeOut, result: list[dict]):
            result.append(node.model_dump(mode="json"))
            for child in node.children:
                flatten(child, result)

        flat_tree = []
        for root in roots:
            flatten(root, flat_tree)

        return flat_tree

    async def api_category_with_children(self) -> dict:
        categories = await self.crud.get_tree_categories()
        all_cats: dict[int, CategoryTreeOut] = {
            cat.id: CategoryTreeOut.model_validate(cat) for cat in categories
        }
        for _, cat in all_cats.items():
            if cat.parent_id and cat.parent_id in all_cats:
                parent = all_cats[cat.parent_id]
                parent.children.append(cat)
        return all_cats

    async def api_create_category_by_name(
        self, name: str, parent_id: int | None, is_active: bool
    ) -> Category:
        category = await self.crud.get_category_name(name)
        if category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Категория с таким названием уже существует",
            )
        if parent_id:
            parent = await self.crud.get_by_id(parent_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Родительская категория не найдена",
                )

        return await self.crud.create(
            {"name": name, "parent_id": parent_id, "is_active": is_active}
        )

    async def api_update_category_by_id(  # noqa: C901
        self, category_id: int, name: str, parent_id: int | None, is_active: bool
    ) -> Category:
        category = await self.crud.get_by_id(category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Категория {category_id} не найдена",
            )

        if parent_id is not None:
            if parent_id == category_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Категория не может быть своей собственной родительской",
                )

            parent = await self.crud.get_by_id(parent_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Родительская категория не найдена",
                )

        if name and name != category.name:
            existing = await self.crud.get_category_name(name)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Категория с '{name}' уже существует",
                )

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if parent_id is not None:
            update_data["parent_id"] = parent_id
        if is_active is not None:
            update_data["is_active"] = is_active

        if not update_data:
            return category

        updated_category = await self.crud.update(category, update_data)
        return updated_category

    async def api_inactive_category_by_id(self, category_id: int) -> str:
        category = await self.crud.get_by_id(category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Категория {category_id} не найдена",
            )
        category_inactive = await self.crud.inactive_category(category.id)
        return (
            f"Категория {category_inactive.name} id: {category_inactive.id} не активена"
        )
