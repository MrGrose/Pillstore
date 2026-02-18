"""Удалить колонку expiry_at из products (срок годности только в партиях).

Revision ID: c2_drop_expiry_at
Revises: b1_product_batches
Create Date: 2026-02-18

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2_drop_expiry_at"
down_revision: Union[str, Sequence[str], None] = "b1_product_batches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("products", "expiry_at", schema=None)


def downgrade() -> None:
    op.add_column(
        "products",
        sa.Column("expiry_at", sa.DateTime(), nullable=True),
        schema=None,
    )
