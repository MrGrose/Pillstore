"""Базовый ревизион (таблицы уже созданы через create_all).

Revision ID: a20e955a6095
Revises:
Create Date: 2026-01-31 21:04:33.723402

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "a20e955a6095"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Базовое состояние схемы — без изменений."""


def downgrade() -> None:
    """Базовое состояние — откат не требуется."""
