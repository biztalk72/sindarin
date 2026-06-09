"""guardrail_overrides table (GP4 / D1)

Revision ID: d142b8071fae
Revises: c7e9a1f04321
Create Date: 2026-06-09 11:35:00.000000

Records admin intent to bypass a guardrail policy: which policy was named, who said so,
why (free-text reason — required at the API layer), when it expires. This PR is audit-only —
the chat path does NOT consult this table yet (so the override is recorded but the policy
keeps running). A follow-up PR (D1b) plugs the active rows into `rag_core.guardrails` so
the bypass actually takes effect; recording the intent first means the audit trail is
complete from day 1 regardless of when the apply-at-runtime side lands.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd142b8071fae'
down_revision: Union[str, None] = 'c7e9a1f04321'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'guardrail_overrides',
        sa.Column('id', sa.Uuid(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('kind', sa.String(length=32), nullable=False),       # 'pii' | 'injection'
        sa.Column('policy_name', sa.String(length=128), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_guardrail_overrides_created_by'),
        sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], name='fk_guardrail_overrides_revoked_by'),
    )
    op.create_index('ix_guardrail_overrides_active', 'guardrail_overrides', ['kind', 'policy_name', 'expires_at'])


def downgrade() -> None:
    op.drop_index('ix_guardrail_overrides_active', table_name='guardrail_overrides')
    op.drop_table('guardrail_overrides')
