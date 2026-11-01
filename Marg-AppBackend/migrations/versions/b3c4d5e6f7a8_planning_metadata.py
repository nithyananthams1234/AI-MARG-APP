"""planning metadata for mentor intelligence (additive)

* schools.block, schools.travel_minutes_from_base
* mentor_tasks.category, mentor_tasks.estimated_minutes

Revision ID: b3c4d5e6f7a8
Revises: a1f0c2d4e5b6
Create Date: 2026-10-31 23:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a1f0c2d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("schools", sa.Column("block", sa.String(length=100), nullable=True))
    op.add_column("schools", sa.Column("travel_minutes_from_base", sa.Integer(), nullable=True))
    op.add_column("mentor_tasks", sa.Column("category", sa.String(length=50), nullable=True))
    op.add_column("mentor_tasks", sa.Column("estimated_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("mentor_tasks", "estimated_minutes")
    op.drop_column("mentor_tasks", "category")
    op.drop_column("schools", "travel_minutes_from_base")
    op.drop_column("schools", "block")
