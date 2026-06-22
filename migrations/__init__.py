"""
Migrations module for quro database schema updates.

Usage:
    from migrations import migrate
    migrate(workspace)
"""

from pathlib import Path


def migrate(workspace: Path) -> int:
    """Run all pending migrations.

    Args:
        workspace: Workspace root directory

    Returns:
        0 on success, non-zero on failure
    """
    from migrations._001_add_tda_columns import migrate as migrate_001

    print("[Migration] Running pending migrations...")

    result = migrate_001(workspace)
    if result != 0:
        return result

    print("[Migration] All migrations complete.")
    return 0