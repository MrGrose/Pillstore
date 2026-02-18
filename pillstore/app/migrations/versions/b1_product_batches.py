"""Партии товара (product_batches, batch_deductions).

Revision ID: b1_product_batches
Revises: a20e955a6095
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "b1_product_batches"
down_revision: Union[str, Sequence[str], None] = "a20e955a6095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, name: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :t"
        ),
        {"t": name},
    )
    return r.scalar() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "product_batches"):
        op.create_table(
            "product_batches",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "product_id",
                sa.Integer(),
                sa.ForeignKey("products.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("expiry_date", sa.Date(), nullable=True),
            sa.Column(
                "quantity",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("batch_code", sa.String(64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_product_batches_product_id",
            "product_batches",
            ["product_id"],
            unique=False,
        )

    if not _table_exists(conn, "batch_deductions"):
        op.create_table(
            "batch_deductions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "batch_id",
                sa.Integer(),
                sa.ForeignKey("product_batches.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "order_id",
                sa.Integer(),
                sa.ForeignKey("orders.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "order_item_id",
                sa.Integer(),
                sa.ForeignKey("order_items.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_batch_deductions_batch_id",
            "batch_deductions",
            ["batch_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("batch_deductions")
    op.drop_table("product_batches")
