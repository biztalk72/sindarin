"""dsr_requests table (GP4 / D2)

Revision ID: f9a4d8c1e527
Revises: d142b8071fae
Create Date: 2026-06-09 12:55:00.000000

Tracks user-initiated data-subject requests (export / forget) and admin processing.
D2 lands the model + endpoints + UI; the *actual* export bundle assembly and the
forget-execution worker are the body of the request handler in the same PR — kept narrow
so each side is reviewable separately.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f9a4d8c1e527'
down_revision: Union[str, None] = 'd142b8071fae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dsr_requests',
        sa.Column('id', sa.Uuid(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('requester_id', sa.Uuid(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),       # 'export' | 'forget'
        sa.Column('status', sa.String(length=16), nullable=False, server_default='pending'),  # pending|processing|completed|rejected
        sa.Column('scope', postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # optional scope filter (e.g. {"chat": true})
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processed_by', sa.Uuid(), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),  # export metadata or forget summary
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id'], name='fk_dsr_requester'),
        sa.ForeignKeyConstraint(['processed_by'], ['users.id'], name='fk_dsr_processed_by'),
    )
    op.create_index('ix_dsr_requests_status', 'dsr_requests', ['status', 'created_at'])
    op.create_index('ix_dsr_requests_requester', 'dsr_requests', ['requester_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_dsr_requests_requester', table_name='dsr_requests')
    op.drop_index('ix_dsr_requests_status', table_name='dsr_requests')
    op.drop_table('dsr_requests')
