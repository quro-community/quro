"""
Database migration utilities.

Provides helpers for running Alembic migrations programmatically.
"""
import os
import subprocess
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database migrations using Alembic"""

    def __init__(self, alembic_ini_path: Optional[str] = None):
        """
        Initialize migration manager

        Args:
            alembic_ini_path: Path to alembic.ini file (default: project root)
        """
        if alembic_ini_path is None:
            # Default to project root
            project_root = Path(__file__).parent.parent.parent
            alembic_ini_path = str(project_root / "alembic.ini")

        self.alembic_ini_path = alembic_ini_path

        if not Path(self.alembic_ini_path).exists():
            raise FileNotFoundError(f"Alembic config not found: {self.alembic_ini_path}")

    def _run_alembic_command(self, *args: str) -> subprocess.CompletedProcess:
        """
        Run alembic command

        Args:
            *args: Alembic command arguments

        Returns:
            Completed process result

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        cmd = ["alembic", "-c", self.alembic_ini_path] + list(args)
        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        if result.stdout:
            logger.info(result.stdout)
        if result.stderr:
            logger.warning(result.stderr)

        return result

    def upgrade(self, revision: str = "head") -> None:
        """
        Upgrade database to a later version

        Args:
            revision: Target revision (default: "head" for latest)
        """
        try:
            self._run_alembic_command("upgrade", revision)
            logger.info(f"Database upgraded to {revision}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Migration upgrade failed: {e.stderr}")
            raise

    def downgrade(self, revision: str = "-1") -> None:
        """
        Downgrade database to a previous version

        Args:
            revision: Target revision (default: "-1" for one step back)
        """
        try:
            self._run_alembic_command("downgrade", revision)
            logger.info(f"Database downgraded to {revision}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Migration downgrade failed: {e.stderr}")
            raise

    def current(self) -> str:
        """
        Get current database revision

        Returns:
            Current revision ID
        """
        try:
            result = self._run_alembic_command("current")
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get current revision: {e.stderr}")
            raise

    def history(self) -> str:
        """
        Get migration history

        Returns:
            Migration history as string
        """
        try:
            result = self._run_alembic_command("history")
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get migration history: {e.stderr}")
            raise

    def revision(self, message: str, autogenerate: bool = False) -> None:
        """
        Create a new migration revision

        Args:
            message: Migration description
            autogenerate: Auto-generate migration from model changes
        """
        try:
            args = ["revision", "-m", message]
            if autogenerate:
                args.append("--autogenerate")

            self._run_alembic_command(*args)
            logger.info(f"Created new migration: {message}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create migration: {e.stderr}")
            raise

    def stamp(self, revision: str = "head") -> None:
        """
        Stamp database with a revision without running migrations

        Args:
            revision: Target revision to stamp
        """
        try:
            self._run_alembic_command("stamp", revision)
            logger.info(f"Database stamped with {revision}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stamp database: {e.stderr}")
            raise


def run_migrations(db_url: Optional[str] = None) -> None:
    """
    Run all pending migrations

    Args:
        db_url: Database URL (default: from QURO_DB_URL env var)
    """
    # Set database URL in environment if provided
    if db_url:
        os.environ["QURO_DB_URL"] = db_url

    manager = MigrationManager()
    manager.upgrade("head")


def create_migration(message: str, autogenerate: bool = False) -> None:
    """
    Create a new migration

    Args:
        message: Migration description
        autogenerate: Auto-generate migration from model changes
    """
    manager = MigrationManager()
    manager.revision(message, autogenerate)


def get_current_revision() -> str:
    """
    Get current database revision

    Returns:
        Current revision ID
    """
    manager = MigrationManager()
    return manager.current()
