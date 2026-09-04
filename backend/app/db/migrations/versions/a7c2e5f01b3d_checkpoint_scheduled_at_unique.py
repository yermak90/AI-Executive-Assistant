"""add (commitment_id, scheduled_at) unique constraint on checkpoints (PRD §31 P1-3)

Revision ID: a7c2e5f01b3d
Revises: f3a1c9d2e4b7
Create Date: 2026-09-04 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c2e5f01b3d'
down_revision: Union[str, None] = 'f3a1c9d2e4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_commitment_checkpoints_commitment_scheduled_at',
        'commitment_checkpoints',
        ['commitment_id', 'scheduled_at'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_commitment_checkpoints_commitment_scheduled_at',
        'commitment_checkpoints',
        type_='unique',
    )
