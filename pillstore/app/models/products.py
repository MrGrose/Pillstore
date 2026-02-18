from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import product_categories


class Product(Base):
    __tablename__ = "products"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str] = mapped_column(String(100))
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    url: Mapped[str | None] = mapped_column(String(255), unique=True)
    image_url: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    seller: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="products"
    )
    cart_items: Mapped[list["CartItem"]] = relationship(  # noqa: F821
        "CartItem", back_populates="product", cascade="all, delete-orphan"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(  # noqa: F821
        "OrderItem", back_populates="product"
    )

    description_left: Mapped[str | None] = mapped_column(Text)
    description_right: Mapped[str | None] = mapped_column(Text)
    mpn: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, server_default=func.now()
    )
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    categories = relationship(
        "Category", secondary=product_categories, back_populates="products"
    )
    category_id: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer),
        nullable=True,
        default=list,
    )

    tsv: Mapped[TSVECTOR] = mapped_column(
        TSVECTOR,
        Computed(
            """
            setweight(to_tsvector('english', coalesce(brand, '')), 'A')
            || setweight(to_tsvector('russian', coalesce(brand, '')), 'A')
            || setweight(to_tsvector('english', coalesce(name, '')), 'B')
            || setweight(to_tsvector('russian', coalesce(name, '')), 'B')
            || setweight(to_tsvector('english', coalesce(description_left, '')), 'C')
            || setweight(to_tsvector('russian', coalesce(description_left, '')), 'C')
            || setweight(to_tsvector('english', coalesce(description_right, '')), 'C')
            || setweight(to_tsvector('russian', coalesce(description_right, '')), 'C')
            """,
            persisted=True,
        ),
        nullable=False,
    )

    table_args__ = (Index("ix_products_tsv_gin", "tsv", postgresql_using="gin"),)
