"""audit_logs observability + documents classification (GP1)

Revision ID: c7e9a1f04321
Revises: a5e8e247a5a0
Create Date: 2026-06-09 02:10:00.000000

Adds the columns GP1 (Observability boost) needs:
  audit_logs   + event_id  VARCHAR(26)  NULL  -- ULID, shared key with daily file log (GP2)
               + trace_id  VARCHAR(64)  NULL  -- chat retrieval_trace_id and similar
               + kind      VARCHAR(64)  NULL  -- 'chat.request' / 'document.upload' / ...
               + outcome   VARCHAR(16)  NULL  -- 'ok'|'error'|'denied'|'timeout'|'dropped'
               + metrics   JSONB        NULL  -- {duration_ms, model, groundedness, guardrails}
  documents    + classified_by   UUID  NULL  -> users.id
               + classified_at   TIMESTAMPTZ NULL
               + retention_until TIMESTAMPTZ NULL  -- GP3 retention worker honors this

All new columns are nullable so existing rows survive without backfill.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c7e9a1f04321'
down_revision: Union[str, None] = 'a5e8e247a5a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('event_id', sa.String(length=26), nullable=True))
    op.add_column('audit_logs', sa.Column('trace_id', sa.String(length=64), nullable=True))
    op.add_column('audit_logs', sa.Column('kind', sa.String(length=64), nullable=True))
    op.add_column('audit_logs', sa.Column('outcome', sa.String(length=16), nullable=True))
    op.add_column('audit_logs', sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index('ix_audit_logs_created_kind', 'audit_logs', [sa.text('created_at DESC'), 'kind'])
    op.create_index('ix_audit_logs_event_id', 'audit_logs', ['event_id'])

    op.add_column('documents', sa.Column('classified_by', sa.Uuid(), nullable=True))
    op.add_column('documents', sa.Column('classified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documents', sa.Column('retention_until', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        'fk_documents_classified_by_users',
        'documents', 'users',
        ['classified_by'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_documents_classified_by_users', 'documents', type_='foreignkey')
    op.drop_column('documents', 'retention_until')
    op.drop_column('documents', 'classified_at')
    op.drop_column('documents', 'classified_by')

    op.drop_index('ix_audit_logs_event_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_created_kind', table_name='audit_logs')
    op.drop_column('audit_logs', 'metrics')
    op.drop_column('audit_logs', 'outcome')
    op.drop_column('audit_logs', 'kind')
    op.drop_column('audit_logs', 'trace_id')
    op.drop_column('audit_logs', 'event_id')
