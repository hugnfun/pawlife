"""Alembic 迁移脚本模板。

每个迁移脚本都基于此模板生成。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = Union[str, None]
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ${upgrades}


def downgrade() -> None:
    ${downgrades}
