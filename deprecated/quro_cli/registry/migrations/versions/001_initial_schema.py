"""
Initial schema migration - create all tables.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
from pathlib import Path


# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial schema"""
    # Read schema.sql file
    schema_path = Path(__file__).parent.parent / "schema.sql"
    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    # Execute schema
    op.execute(schema_sql)


def downgrade() -> None:
    """Drop all tables"""
    # Drop tables in reverse dependency order
    op.execute("DROP TABLE IF EXISTS qra_chains CASCADE")
    op.execute("DROP TABLE IF EXISTS workspace_scans CASCADE")
    op.execute("DROP TABLE IF EXISTS twin_simulations CASCADE")
    op.execute("DROP TABLE IF EXISTS shadow_drafts CASCADE")
    op.execute("DROP TABLE IF EXISTS cqe_reflections CASCADE")
    op.execute("DROP TABLE IF EXISTS cqe_edges CASCADE")
    op.execute("DROP TABLE IF EXISTS cqe_categories CASCADE")
    op.execute("DROP TABLE IF EXISTS nrt_alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS pitfall_matches CASCADE")
    op.execute("DROP TABLE IF EXISTS pitfalls CASCADE")
    op.execute("DROP TABLE IF EXISTS lsh_config CASCADE")
    op.execute("DROP TABLE IF EXISTS lsh_bands CASCADE")
    op.execute("DROP TABLE IF EXISTS dependencies CASCADE")
    op.execute("DROP TABLE IF EXISTS exports CASCADE")
    op.execute("DROP TABLE IF EXISTS imports CASCADE")
    op.execute("DROP TABLE IF EXISTS symbols CASCADE")
    op.execute("DROP TABLE IF EXISTS files CASCADE")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE")

    # Drop extensions
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS \"uuid-ossp\"")
