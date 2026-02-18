"""Партии товара (по срокам годности) и списания по заказам (FIFO)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProductBatch(Base):
    __tablename__ = "product_batches"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expiry_date: Mapped[date | None] = mapped_column(nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    batch_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    product: Mapped["Product"] = relationship(  # noqa: F821
        "Product", back_populates="batches"
    )
    deductions: Mapped[list["BatchDeduction"]] = relationship(
        "BatchDeduction",
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class BatchDeduction(Base):
    __tablename__ = "batch_deductions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("product_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    batch: Mapped["ProductBatch"] = relationship(
        "ProductBatch", back_populates="deductions"
    )
