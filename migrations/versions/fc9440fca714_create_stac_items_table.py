"""create stac_items table

Revision ID: fc9440fca714
Revises: 
Create Date: 2026-10-18 19:48:19.249533

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fc9440fca714'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.execute(
        """
        CREATE TABLE stac_items
        (
            collection       text        NOT NULL,
            id               text        NOT NULL,
            item             jsonb       NOT NULL,
            geometry         geometry(Geometry, 4326),
            start_datetime   timestamptz NOT NULL,
            end_datetime     timestamptz NOT NULL,
            cloud_cover      double precision,
            processing_level text,
            created_at       timestamptz NOT NULL DEFAULT now(),
            updated_at       timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (collection, id),
            CONSTRAINT stac_items_cloud_cover_range CHECK (cloud_cover BETWEEN 0 AND 100)
        )
        """
    )

    op.execute("CREATE INDEX stac_items_geometry_idx ON stac_items USING gist (geometry)")
    op.execute("CREATE INDEX stac_items_datetime_idx ON stac_items (start_datetime, end_datetime)")
    op.execute("CREATE INDEX stac_items_cloud_cover_idx ON stac_items (cloud_cover)")
    op.execute("CREATE INDEX stac_items_processing_level_idx ON stac_items (processing_level)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE stac_items")
