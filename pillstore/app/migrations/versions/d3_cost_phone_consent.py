from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3_cost_phone_consent"
down_revision: Union[str, Sequence[str], None] = "c2_drop_expiry_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("cost", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "order_items",
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("contact_phone", sa.String(20), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("personal_data_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("orders", "personal_data_consent")
    op.drop_column("orders", "contact_phone")
    op.drop_column("order_items", "unit_cost")
    op.drop_column("products", "cost")
