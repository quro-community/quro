"""
CQE Maintenance Commands - Backup and restore tools

@module quro_cli.commands.cqe_maintenance
@intent Provide tools for CQE index backup, restore, and maintenance
"""

import click
import shutil
from pathlib import Path
from datetime import datetime


# Plugin metadata
METADATA = {
    'description': 'CQE Maintenance - Backup, restore, and safety tools',
    'commands': {
        'cqe-backup': {
            'description': 'Backup CQE index',
            'usage': 'quro cqe-backup [--output backups/]',
            'implementation': 'quro_cli/commands/cqe_maintenance.py:cqe_backup'
        },
        'cqe-restore': {
            'description': 'Restore CQE index from backup',
            'usage': 'quro cqe-restore [--backup-file backups/cqe_index_20260408.db]',
            'implementation': 'quro_cli/commands/cqe_maintenance.py:cqe_restore'
        },
        'cqe-status': {
            'description': 'Show CQE index status and health',
            'usage': 'quro cqe-status',
            'implementation': 'quro_cli/commands/cqe_maintenance.py:cqe_status'
        },
        'cqe-scan': {
            'description': 'Scan CQE index for garbage data and quality issues',
            'usage': 'quro cqe-scan [--clean]',
            'implementation': 'quro_cli/commands/cqe_maintenance.py:cqe_scan'
        }
    }
}


def register(cli: click.Group):
    """Register maintenance commands"""
    cli.add_command(cqe_backup)
    cli.add_command(cqe_restore)
    cli.add_command(cqe_status)
    cli.add_command(cqe_scan)


@click.command('cqe-backup')
@click.option('--output-dir', type=click.Path(),
              default='.quro_context/backups',
              help='Backup directory')
def cqe_backup(output_dir: str):
    """Backup CQE index to timestamped file"""
    index_path = Path('.quro_context/cqe_index.db')
    output_dir = Path(output_dir)

    click.echo("💾 CQE Index Backup")
    click.echo("="*60)

    if not index_path.exists():
        click.echo(f"\n❌ CQE index not found: {index_path}", err=True)
        return

    # Create backup directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = output_dir / f"cqe_index_{timestamp}.db"

    # Copy index
    click.echo(f"\n📋 Backing up: {index_path}")
    click.echo(f"📁 To: {backup_file}")

    shutil.copy2(str(index_path), str(backup_file))

    # Get file size
    size_mb = backup_file.stat().st_size / (1024 * 1024)

    click.echo(f"\n✅ Backup complete!")
    click.echo(f"  File: {backup_file}")
    click.echo(f"  Size: {size_mb:.2f} MB")

    # Also backup .backup file if exists
    backup_backup = index_path.with_suffix('.backup')
    if backup_backup.exists():
        backup_backup_file = output_dir / f"cqe_index_{timestamp}.backup"
        shutil.copy2(str(backup_backup), str(backup_backup_file))
        click.echo(f"  Also backed up: {backup_backup_file.name}")


@click.command('cqe-restore')
@click.option('--backup-file', type=click.Path(exists=True),
              required=True,
              help='Backup file to restore from')
@click.option('--force', is_flag=True,
              help='Force restore without confirmation')
def cqe_restore(backup_file: str, force: bool):
    """Restore CQE index from backup"""
    backup_path = Path(backup_file)
    index_path = Path('.quro_context/cqe_index.db')

    click.echo("♻️  CQE Index Restore")
    click.echo("="*60)

    if not backup_path.exists():
        click.echo(f"\n❌ Backup file not found: {backup_path}", err=True)
        return

    # Show current index status
    if index_path.exists():
        current_size = index_path.stat().st_size / (1024 * 1024)
        click.echo(f"\n⚠️  Current index exists:")
        click.echo(f"  File: {index_path}")
        click.echo(f"  Size: {current_size:.2f} MB")

        if not force:
            if not click.confirm("\nReplace current index with backup?"):
                click.echo("Restore cancelled.")
                return

    # Backup current index before restore
    if index_path.exists():
        safety_backup = index_path.with_suffix('.pre_restore_backup')
        shutil.copy2(str(index_path), str(safety_backup))
        click.echo(f"\n💾 Safety backup created: {safety_backup.name}")

    # Restore from backup
    click.echo(f"\n📋 Restoring from: {backup_path}")
    shutil.copy2(str(backup_path), str(index_path))

    backup_size = backup_path.stat().st_size / (1024 * 1024)

    click.echo(f"\n✅ Restore complete!")
    click.echo(f"  File: {index_path}")
    click.echo(f"  Size: {backup_size:.2f} MB")


@click.command('cqe-scan')
@click.option('--clean', is_flag=True, help='Remove garbage data from the index')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed garbage atom list')
def cqe_scan(clean: bool, verbose: bool):
    """Scan CQE index for garbage data and quality issues.

    Detects:
    - Worktree atoms (from .claude/worktrees/ directories)
    - Oversized features (> MAX_FEATURES=1000)
    - Orphan morphisms (references non-existent atoms)
    - Empty/null features
    - Placeholder symbols
    - Garbage categories (single-character)
    """
    import json
    import sqlite3

    index_path = Path('.quro_context/cqe_index.db')

    click.echo("🔍 CQE Index Garbage Scan")
    click.echo("=" * 60)

    if not index_path.exists():
        click.echo(f"\n❌ CQE index not found: {index_path}", err=True)
        click.echo("Run 'quro cqe-build --force' to create the index.")
        return

    size_mb = index_path.stat().st_size / (1024 * 1024)
    click.echo(f"\n📁 Index: {index_path} ({size_mb:.2f} MB)")

    try:
        conn = sqlite3.connect(str(index_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Load all atoms into memory for fast analysis
        all_atoms = cursor.execute("SELECT id, type, features_json FROM atoms").fetchall()
        atom_ids = {row['id'] for row in all_atoms}

        click.echo(f"📊 Total atoms: {len(all_atoms):,}")

        # ── Garbage Category 1: Worktree atoms ─────────────────────────────────
        # NOTE: atom ids use dots (.) as path separators, NOT slashes (/)
        # e.g. sym::.claude.worktrees.nrt-fix.ca_sidecar...
        worktree_patterns = ['.claude.worktrees', 'worktrees.nrt']
        worktree_atoms = []
        for row in all_atoms:
            for pat in worktree_patterns:
                if pat in row['id']:
                    worktree_atoms.append(row)
                    break

        # ── Garbage Category 2: Oversized features ─────────────────────────────
        MAX_FEATURES = 1000
        oversized_atoms = []
        for row in all_atoms:
            try:
                features = json.loads(row['features_json']) if row['features_json'] else []
                if isinstance(features, list) and len(features) > MAX_FEATURES:
                    oversized_atoms.append((row, len(features)))
            except (json.JSONDecodeError, TypeError):
                pass  # Invalid JSON, will be caught by empty features check

        # ── Garbage Category 3: Empty / null features ────────────────────────────
        empty_feature_atoms = []
        for row in all_atoms:
            try:
                features = json.loads(row['features_json']) if row['features_json'] else None
                if features is None or (isinstance(features, list) and len(features) == 0):
                    empty_feature_atoms.append(row)
            except (json.JSONDecodeError, TypeError):
                empty_feature_atoms.append(row)  # Invalid JSON = empty

        # ── Garbage Category 4: Placeholder symbols ─────────────────────────────
        placeholder_atoms = [row for row in all_atoms if 'Placeholder' in row['id']]

        # ── Garbage Category 5: Garbage categories (single-char) ─────────────────
        garbage_cat_atoms = []
        for row in all_atoms:
            if row['type'] == 'category':
                tag = row['id'].split('::', 1)[1] if '::' in row['id'] else ''
                if len(tag) <= 1:
                    garbage_cat_atoms.append(row)

        # ── Garbage Category 6: Orphan morphisms ─────────────────────────────────
        all_morphisms = cursor.execute(
            "SELECT from_id, to_id, kind FROM morphisms"
        ).fetchall()
        orphan_morphisms = []
        for m in all_morphisms:
            if m['from_id'] not in atom_ids or m['to_id'] not in atom_ids:
                orphan_morphisms.append(m)

        conn.close()

        # ── Summary Report ─────────────────────────────────────────────────────
        click.echo(f"\n📋 Garbage Report:")
        click.echo("-" * 60)

        total_garbage = (
            len(worktree_atoms) + len(oversized_atoms) +
            len(empty_feature_atoms) + len(placeholder_atoms) +
            len(garbage_cat_atoms) + len(orphan_morphisms)
        )
        clean_count = len(all_atoms) - (
            len(worktree_atoms) + len(empty_feature_atoms) +
            len(placeholder_atoms) + len(garbage_cat_atoms)
        )

        click.echo(f"  Worktree atoms:      {len(worktree_atoms):>6,}  ⚠️  From .claude/worktrees/")
        click.echo(f"  Oversized features:   {len(oversized_atoms):>6,}  ⚠️  >{MAX_FEATURES} features per atom")
        click.echo(f"  Empty/null features:  {len(empty_feature_atoms):>6,}  ⚠️  No semantic content")
        click.echo(f"  Placeholder symbols: {len(placeholder_atoms):>6,}  ⚠️  Testing artifacts")
        click.echo(f"  Garbage categories:   {len(garbage_cat_atoms):>6,}  ⚠️  Single-char category tags")
        click.echo(f"  Orphan morphisms:    {len(orphan_morphisms):>6,}  ⚠️  Dangling references")
        click.echo("-" * 60)
        click.echo(f"  TOTAL garbage:       {total_garbage:>6,}  "
                   f"({total_garbage/len(all_atoms)*100:.1f}% of {len(all_atoms):,} atoms)")

        quality_pct = (clean_count / len(all_atoms) * 100) if all_atoms else 0
        if quality_pct >= 95:
            grade = "🟢 A (Excellent)"
        elif quality_pct >= 80:
            grade = "🟡 B (Good)"
        elif quality_pct >= 60:
            grade = "🟠 C (Fair)"
        else:
            grade = "🔴 D (Poor)"

        click.echo(f"\n🏆 Index Quality: {grade} ({quality_pct:.1f}%)")

        # ── Detailed listing (verbose mode) ────────────────────────────────────
        if verbose:
            if worktree_atoms:
                click.echo(f"\n⚠️  Worktree atoms ({len(worktree_atoms)}):")
                for row in worktree_atoms[:20]:
                    click.echo(f"    - {row['id'][:80]}")
                if len(worktree_atoms) > 20:
                    click.echo(f"    ... and {len(worktree_atoms) - 20} more")

            if oversized_atoms:
                click.echo(f"\n⚠️  Oversized features ({len(oversized_atoms)}):")
                for row, count in oversized_atoms[:10]:
                    click.echo(f"    - {row['id'][:60]}: {count} features")
                if len(oversized_atoms) > 10:
                    click.echo(f"    ... and {len(oversized_atoms) - 10} more")

            if placeholder_atoms:
                click.echo(f"\n⚠️  Placeholder symbols ({len(placeholder_atoms)}):")
                for row in placeholder_atoms:
                    click.echo(f"    - {row['id']}")

            if garbage_cat_atoms:
                click.echo(f"\n⚠️  Garbage categories ({len(garbage_cat_atoms)}):")
                for row in garbage_cat_atoms[:20]:
                    click.echo(f"    - {row['id']}")
                if len(garbage_cat_atoms) > 20:
                    click.echo(f"    ... and {len(garbage_cat_atoms) - 20} more")

        # ── Clean operation ────────────────────────────────────────────────────
        if clean:
            click.echo(f"\n🧹 Cleaning garbage data...")

            if not worktree_atoms and not oversized_atoms and not empty_feature_atoms \
               and not placeholder_atoms and not garbage_cat_atoms and not orphan_morphisms:
                click.echo("  ✅ No garbage found. Index is clean.")
                return

            # Create safety backup first
            safety_backup = index_path.with_suffix('.pre_clean_backup')
            import shutil
            shutil.copy2(str(index_path), str(safety_backup))
            click.echo(f"  💾 Safety backup: {safety_backup}")

            # Connect and clean
            conn = sqlite3.connect(str(index_path))
            cursor = conn.cursor()

            deleted_atoms = 0
            deleted_morphisms = 0

            # Collect IDs to delete
            worktree_ids = {row['id'] for row in worktree_atoms}
            empty_ids = {row['id'] for row in empty_feature_atoms}
            placeholder_ids = {row['id'] for row in placeholder_atoms}
            garbage_cat_ids = {row['id'] for row in garbage_cat_atoms}

            atom_ids_to_delete = (
                worktree_ids | empty_ids | placeholder_ids | garbage_cat_ids
            )

            # Delete garbage atoms
            for atom_id in atom_ids_to_delete:
                cursor.execute("DELETE FROM atoms WHERE id = ?", (atom_id,))
                deleted_atoms += cursor.rowcount

            # Delete orphan morphisms
            for m in orphan_morphisms:
                cursor.execute(
                    "DELETE FROM morphisms WHERE from_id = ? AND to_id = ?",
                    (m['from_id'], m['to_id'])
                )
                deleted_morphisms += cursor.rowcount

            conn.commit()
            conn.close()

            click.echo(f"  ✅ Deleted {deleted_atoms:,} garbage atoms")
            click.echo(f"  ✅ Deleted {deleted_morphisms:,} orphan morphisms")
            click.echo(f"  ✅ Run 'quro cqe-build --force' to rebuild with clean data.")
        else:
            if total_garbage > 0:
                click.echo(f"\n💡 Run 'quro cqe-scan --clean' to remove garbage data.")

    except Exception as e:
        import traceback
        click.echo(f"\n❌ Scan failed: {e}", err=True)
        if verbose:
            traceback.print_exc()


@click.command('cqe-status')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed statistics')
def cqe_status(verbose: bool):
    """Show CQE index status and health"""
    import sqlite3
    import json

    index_path = Path('.quro_context/cqe_index.db')
    backup_path = index_path.with_suffix('.backup')

    click.echo("📊 CQE Index Status")
    click.echo("="*60)

    # Check main index
    if not index_path.exists():
        click.echo(f"\n❌ CQE index not found: {index_path}")
        click.echo("Run 'quro cqe-build' to create the index.")
        return

    # Get file info
    size_mb = index_path.stat().st_size / (1024 * 1024)
    mtime = datetime.fromtimestamp(index_path.stat().st_mtime)

    click.echo(f"\n📁 Main Index:")
    click.echo(f"  Path: {index_path}")
    click.echo(f"  Size: {size_mb:.2f} MB")
    click.echo(f"  Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

    # Check backup
    if backup_path.exists():
        backup_size = backup_path.stat().st_size / (1024 * 1024)
        backup_mtime = datetime.fromtimestamp(backup_path.stat().st_mtime)
        click.echo(f"\n💾 Backup Index:")
        click.echo(f"  Path: {backup_path}")
        click.echo(f"  Size: {backup_size:.2f} MB")
        click.echo(f"  Modified: {backup_mtime.strftime('%Y-%m-%d %H:%M:%S')}")

    # Get index stats
    try:
        conn = sqlite3.connect(str(index_path))
        cursor = conn.cursor()

        atoms_count = cursor.execute("SELECT COUNT(*) FROM atoms").fetchone()[0]
        morphisms_count = cursor.execute("SELECT COUNT(*) FROM morphisms").fetchone()[0]
        payloads_count = cursor.execute("SELECT COUNT(*) FROM payloads").fetchone()[0]

        # Check MinHash coverage
        minhash_count = cursor.execute(
            "SELECT COUNT(*) FROM atoms WHERE minhash_blob IS NOT NULL"
        ).fetchone()[0]
        minhash_pct = (minhash_count / atoms_count * 100) if atoms_count > 0 else 0

        # Get metadata
        try:
            build_ts = cursor.execute(
                "SELECT value FROM metadata WHERE key = 'build_timestamp'"
            ).fetchone()
            if build_ts:
                build_time = datetime.fromtimestamp(int(build_ts[0]))
                build_time_str = build_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                build_time_str = "Unknown"
        except:
            build_time_str = "Unknown"

        conn.close()

        click.echo(f"\n📊 Index Statistics:")
        click.echo(f"  Atoms: {atoms_count:,}")
        click.echo(f"  Morphisms: {morphisms_count:,}")
        click.echo(f"  Payloads: {payloads_count:,}")
        click.echo(f"  MinHash coverage: {minhash_pct:.1f}% ({minhash_count:,}/{atoms_count:,})")
        click.echo(f"  Avg morphisms/atom: {morphisms_count/atoms_count:.2f}" if atoms_count > 0 else "  Avg morphisms/atom: 0")
        click.echo(f"  Built: {build_time_str}")

        # Health check
        click.echo(f"\n🏥 Health Check:")
        issues = []

        if minhash_pct < 80:
            issues.append(f"Low MinHash coverage ({minhash_pct:.1f}% < 80%)")

        if morphisms_count / atoms_count < 5 if atoms_count > 0 else True:
            issues.append(f"Low morphism connectivity ({morphisms_count/atoms_count:.2f} < 5)")

        if payloads_count == 0:
            issues.append("No payloads preloaded")

        if issues:
            click.echo("  ⚠️  Issues found:")
            for issue in issues:
                click.echo(f"    - {issue}")
        else:
            click.echo("  ✅ All checks passed")

    except Exception as e:
        click.echo(f"\n❌ Failed to read index: {e}", err=True)

    # List available backups
    backup_dir = Path('.quro_context/backups')
    if backup_dir.exists():
        backups = sorted(backup_dir.glob('cqe_index_*.db'), reverse=True)
        if backups:
            click.echo(f"\n📦 Available Backups ({len(backups)}):")
            for i, backup in enumerate(backups[:5], 1):
                backup_size = backup.stat().st_size / (1024 * 1024)
                backup_mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                click.echo(f"  {i}. {backup.name} ({backup_size:.2f} MB, {backup_mtime.strftime('%Y-%m-%d %H:%M')})")
            if len(backups) > 5:
                click.echo(f"  ... and {len(backups) - 5} more")
