from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import product_categories


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    parent: Mapped["Category"] = relationship(
        "Category", back_populates="children", remote_side="Category.id"
    )
    children: Mapped[list["Category"]] = relationship(
        "Category", back_populates="parent"
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    products = relationship(
        "Product", secondary=product_categories, back_populates="categories"
    )
