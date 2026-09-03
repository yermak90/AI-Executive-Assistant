"""add voice_captures (Sprint 2 — Voice Note AI Capture)

Revision ID: f3a1c9d2e4b7
Revises: d18eaa00d57a
Create Date: 2026-09-03 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3a1c9d2e4b7'
down_revision: Union[str, None] = 'd18eaa00d57a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'voice_captures',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'UPLOADED', 'TRANSCRIBING', 'EXTRACTING', 'READY_FOR_REVIEW',
                'FAILED', 'CONFIRMED', 'DISCARDED', 'EXPIRED',
                name='voice_capture_status', native_enum=False, length=32,
            ),
            nullable=False,
        ),
        sa.Column('language_code', sa.String(length=16), nullable=True),
        sa.Column('audio_storage_key', sa.String(length=255), nullable=True),
        sa.Column('audio_mime_type', sa.String(length=100), nullable=False),
        sa.Column('audio_size_bytes', sa.Integer(), nullable=False),
        sa.Column('audio_duration_ms', sa.Integer(), nullable=True),
        sa.Column('transcript_text', sa.Text(), nullable=True),
        sa.Column('candidate_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('stt_provider', sa.String(length=64), nullable=True),
        sa.Column('stt_model', sa.String(length=128), nullable=True),
        sa.Column('extraction_provider', sa.String(length=64), nullable=True),
        sa.Column('extraction_model', sa.String(length=128), nullable=True),
        sa.Column('processing_attempts', sa.Integer(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('confirmed_commitment_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('discarded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['confirmed_commitment_id'], ['commitments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_voice_captures_idempotency_key'),
        sa.UniqueConstraint('confirmed_commitment_id', name='uq_voice_captures_confirmed_commitment_id'),
    )
    op.create_index(op.f('ix_voice_captures_status'), 'voice_captures', ['status'], unique=False)
    op.create_index(op.f('ix_voice_captures_expires_at'), 'voice_captures', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_voice_captures_expires_at'), table_name='voice_captures')
    op.drop_index(op.f('ix_voice_captures_status'), table_name='voice_captures')
    op.drop_table('voice_captures')
    op.execute("DROP TYPE IF EXISTS voice_capture_status")
