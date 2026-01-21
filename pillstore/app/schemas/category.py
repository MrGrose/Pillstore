from pydantic import BaseModel, ConfigDict, Field

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class CategoryCreate(CategoryBase):
    parent_id: int | None = Field(None, ge=1)

class CategoryRead(CategoryBase):
    id: int
    is_active: bool = True
    parent_id: int | None = None
    product_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)

class CategoriesSchema(BaseModel):
    id: int
    name: str
    is_active: bool
    parent_id: int | None = None
    
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class CategoryTreeOut(BaseModel):
    id: int
    name: str
    parent_id: int | None = None
    level: int = 0
    path: list[int] = Field(default_factory=list)
    is_active: bool
    
    children: list['CategoryTreeOut'] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=False)