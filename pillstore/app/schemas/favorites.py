from pydantic import BaseModel, Field


class MergeFavoritesBody(BaseModel):
    product_ids: list[int] = []


class ToggleFavoriteBody(BaseModel):
    product_id: int = Field(..., ge=1)


class FavoritesIdsResponse(BaseModel):
    product_ids: list[int]


class ToggleFavoriteResponse(BaseModel):
    in_favorites: bool
