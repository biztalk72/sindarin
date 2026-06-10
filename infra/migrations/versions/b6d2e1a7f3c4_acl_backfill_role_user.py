"""acl_entries: backfill role='user' read grant for PUBLIC/INTERNAL docs

Revision ID: b6d2e1a7f3c4
Revises: e3f1c2b8a4d7
Create Date: 2026-06-10 00:30:00.000000

Companion to ``e3f1c2b8a4d7``: that revision made role principals representable, and
``apps/api/app/ingest.py`` now writes a ``('role', 'user')`` read grant alongside the per-
owner grant for any PUBLIC or INTERNAL upload. Documents uploaded before the code change
still only have the owner-user grant, so a non-admin caller still sees "no authorized
documents matched the query" against them.

This migration inserts the missing role-user grant for those existing PUBLIC/INTERNAL docs.
It is idempotent — re-running is a no-op because of the new unique constraint
``uq_acl_entries_resource_principal_permission``.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b6d2e1a7f3c4'
down_revision: Union[str, None] = 'e3f1c2b8a4d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO acl_entries (id, resource_id, resource_type, principal_type,
                                 principal_id, permission)
        SELECT gen_random_uuid(), d.id, 'document', 'role', 'user', 'read'
          FROM documents d
         WHERE d.security_level IN ('public', 'internal')
        ON CONFLICT ON CONSTRAINT uq_acl_entries_resource_principal_permission DO NOTHING
        """
    )


def downgrade() -> None:
    # Reverse only the rows this migration could have created — role/user/read grants on
    # PUBLIC/INTERNAL docs. Don't touch per-user grants or any rows on other security levels.
    op.execute(
        """
        DELETE FROM acl_entries
         WHERE principal_type = 'role'
           AND principal_id = 'user'
           AND permission = 'read'
           AND resource_type = 'document'
           AND resource_id IN (
               SELECT id FROM documents WHERE security_level IN ('public', 'internal')
           )
        """
    )
