from typing import Sequence, Union


revision: str = "a20e955a6095"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Базовое состояние схемы — без изменений."""


def downgrade() -> None:
    """Базовое состояние — откат не требуется."""
