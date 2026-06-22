"""StorageCoordinator — DuckDB connection and lifecycle manager.

@module quro.storage.coordinator
@intent Open/close DuckDB connection; coordinate table initialization;
        expose query handle
@role Orchestrator (coordination, delegation)
"""

import logging
from pathlib import Path
from typing import Optional

import duckdb

from storage.schema import TdaSchema
from storage.migration import MigrationRunner

logger = logging.getLogger(__name__)

__all__ = ["StorageCoordinator"]


class StorageCoordinator:
    """Manages DuckDB connection lifecycle for TDA storage.

    Invariants:
      - Single writer at a time; WAL disabled (batch pipeline)
      - Creates DB + runs migration on first open
      - Connection pool semantics: one connection per instance

    Lifecycle:
      - Created at pipeline start, closed at pipeline end
      - Single instance per run
    """

    def __init__(self, db_path: Path):
        """Initialize storage coordinator.

        Args:
            db_path: Path to quro_tda.duckdb
        """
        self.db_path = db_path
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._initialized = False

    def ensure_initialized(self) -> None:
        """Create DB if missing, run migration, validate schema version.

        Raises:
            RuntimeError: If migration fails.
        """
        if self._initialized:
            return

        logger.info("StorageCoordinator: ensuring initialization for %s", self.db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        runner = MigrationRunner(self.db_path)
        if not runner.run():
            raise RuntimeError(
                f"Failed to initialize/migrate DuckDB at {self.db_path}"
            )

        self._initialized = True

    def open(self) -> duckdb.DuckDBPyConnection:
        """Open and return a DuckDB connection.

        Validates schema version on first open.

        Returns:
            Active DuckDB connection.

        Raises:
            RuntimeError: If initialization fails.
        """
        if self._conn is not None:
            return self._conn

        self.ensure_initialized()

        self._conn = duckdb.connect(str(self.db_path))
        self._conn.execute("PRAGMA threads=4")

        self._validate_schema_version()

        logger.info("StorageCoordinator: connection opened")
        return self._conn

    def close(self) -> None:
        """Close the DuckDB connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("StorageCoordinator: connection closed")

    def _validate_schema_version(self) -> None:
        """Validate that the schema version matches expected."""
        if self._conn is None:
            return
        try:
            result = self._conn.execute(
                TdaSchema.version_sql()
            ).fetchone()
            if result:
                version = int(result[0])
                if version != TdaSchema.CURRENT_VERSION:
                    logger.warning(
                        "Schema version mismatch: DB=%d, expected=%d",
                        version, TdaSchema.CURRENT_VERSION,
                    )
        except Exception:
            logger.debug("No _meta table found; schema may not be initialized")

    @property
    def connection(self) -> Optional[duckdb.DuckDBPyConnection]:
        """Current connection (may be None if not opened)."""
        return self._conn

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()
