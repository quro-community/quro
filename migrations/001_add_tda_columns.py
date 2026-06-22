#!/usr/bin/env python3
"""
Migration 001: Add TDA columns to nodes table

Adds energy field columns required for TDA navigation:
- energy_total: Total energy at node
- field_role: Role in field (attractor, repeller, saddle_point, etc.)
- field_magnitude: Field strength magnitude
- mass: Cognitive mass
- friction: Flow friction coefficient

Usage:
    python migrations/001_add_tda_columns.py [--workspace PATH]
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def migrate(workspace: Path) -> int:
    """Run migration."""
    registry_db = workspace / ".quro_context" / "registry.db"

    if not registry_db.exists():
        print(f"[Error] Registry database not found: {registry_db}")
        return 1

    print(f"Migration 001: Add TDA columns to nodes table")
    print(f"  Registry: {registry_db}")
    print()

    conn = sqlite3.connect(registry_db)
    cursor = conn.cursor()

    # Get current columns
    cursor.execute("PRAGMA table_info(nodes)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Required TDA columns
    tda_columns = {
        "energy_total": "REAL",
        "field_role": "TEXT",
        "field_magnitude": "REAL", 
        "mass": "REAL",
        "friction": "REAL",
    }

    added_columns = []
    skipped_columns = []

    for col_name, col_type in tda_columns.items():
        if col_name in existing_columns:
            skipped_columns.append(col_name)
            continue

        try:
            cursor.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_type}")
            added_columns.append(col_name)
            print(f"  Added column: {col_name} ({col_type})")
        except sqlite3.Error as e:
            print(f"  [Warning] Failed to add {col_name}: {e}")
            skipped_columns.append(col_name)

    conn.commit()
    conn.close()

    print()
    if added_columns:
        print(f"[OK] Added {len(added_columns)} columns: {added_columns}")
    if skipped_columns:
        print(f"[Info] Skipped {len(skipped_columns)} columns (already exist): {skipped_columns}")

    print()
    print("Migration 001 complete.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Add TDA columns to nodes table")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace root directory (default: current directory)"
    )
    args = parser.parse_args()

    return migrate(args.workspace)


if __name__ == "__main__":
    sys.exit(main())
