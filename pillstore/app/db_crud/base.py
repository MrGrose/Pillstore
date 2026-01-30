from typing import TypeVar, Generic
from app.db.base import Base
from pydantic import BaseModel
from sqlalchemy import select


ModelType = TypeVar("ModelType", bound=Base)
SchemaType = TypeVar("SchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType]):
    def __init__(self, session, model) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, id: int):
        db_result = await self.session.scalars(
            select(self.model).where(self.model.id == id)
        )
        result = db_result.first()
        return result

    async def get_all(self, flag):
        db_result_active = await self.session.scalars(
            select(self.model).where(self.model.is_active == flag)
        )
        result_active = list(db_result_active.all())
        return result_active

    async def create(self, obj_in: dict):
        db_obj = self.model(**obj_in)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(self, db_obj: ModelType, obj_in: dict):
        for field, value in obj_in.items():
            setattr(db_obj, field, value)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: int):
        obj = await self.get_by_id(id)
        await self.session.delete(obj)
        await self.session.commit()
        return obj

    async def get_by_name(self, name: str):
        """Поиск по имени (для Category/Product)"""
        if hasattr(self.model, 'name'):
            stmt = select(self.model).where(self.model.name == name)
            result = await self.session.scalars(stmt)
            return result.first()
        return None