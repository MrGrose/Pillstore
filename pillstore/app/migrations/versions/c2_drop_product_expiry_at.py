from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2_drop_expiry_at"
down_revision: Union[str, Sequence[str], None] = "b1_product_batches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE products DROP COLUMN IF EXISTS expiry_at"))


def downgrade() -> None:
    op.add_column(
        "products",
        sa.Column("expiry_at", sa.DateTime(), nullable=True),
        schema=None,
    )
