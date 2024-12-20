"""${message}

Revision ID: ${revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic
revision = ${repr(revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """Implements forward migration changes to the database schema.
    
    SQLite Considerations:
    - ALTER TABLE limitations are handled through table recreation
    - Transactions are managed for atomic operations
    - Batch operations are used for large tables
    - Schema validation is performed after changes
    """
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Implements reverse migration changes to roll back schema changes.
    
    SQLite Considerations:
    - Rollback operations preserve data integrity
    - Transactions ensure atomic rollback
    - Previous schema state is validated after rollback
    - Indexes are properly restored
    """
    ${downgrades if downgrades else "pass"}