"""make stac_items geometry not null

Revision ID: 51e6a7ae869f
Revises: fc9440fca714
Create Date: 2026-10-20 11:39:07.343881

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '51e6a7ae869f'
down_revision: Union[str, Sequence[str], None] = 'fc9440fca714'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE stac_items ALTER COLUMN geometry SET NOT NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE stac_items ALTER COLUMN geometry DROP NOT NULL")
