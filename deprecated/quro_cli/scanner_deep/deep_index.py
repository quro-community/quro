"""
Deep Index — SQLite storage for ClassSignature data.

@module quro_cli.scanner_deep.deep_index
@intent Full rebuild, no incremental update. SQLite in-memory or persisted.

Lifecycle: rebuild on each scan, atomically swapped.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Optional

from quro_cli.scanner_deep.class_signature import ClassSignature

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = ".quro_context/deep_index.db"

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS class_signatures (
    uid TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    class_name TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    explicit_attrs TEXT NOT NULL DEFAULT '[]',
    property_attrs TEXT NOT NULL DEFAULT '[]',
    method_names TEXT NOT NULL DEFAULT '[]',
    observation_scope TEXT NOT NULL DEFAULT 'AST_ONLY',
    scanned_at TEXT NOT NULL
);
"""

_SCHEMA_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_class_sigs_file ON class_signatures(file_path)",
    "CREATE INDEX IF NOT EXISTS idx_class_sigs_name ON class_signatures(class_name)",
]


def _row_to_signature(row: sqlite3.Row) -> ClassSignature:
    """Convert a SQLite row to a ClassSignature."""
    return ClassSignature(
        class_name=row["class_name"],
        file_path=row["file_path"],
        explicit_attrs=tuple(json.loads(row["explicit_attrs"])),
        property_attrs=tuple(json.loads(row["property_attrs"])),
        method_names=tuple(json.loads(row["method_names"])),
        observation_scope=row["observation_scope"],
    )


class DeepIndex:
    """SQLite-backed index of ClassSignature data.

    Modes:
        in_memory: Shared in-memory SQLite via URI. Good for single-file audit.
        persisted: File-based SQLite with atomic swap. Good for workspace audit.

    Connection lifecycle:
        in_memory: single connection held open for the instance lifetime.
        persisted: new connection per method call (safe for cross-call isolation).
    """

    def __init__(self, db_path: Optional[str] = None, in_memory: bool = False):
        if in_memory:
            self._in_memory = True
            self.db_path = "file:deep_index_mem?mode=memory&cache=shared"
            self._conn: Optional[sqlite3.Connection] = self._new_connection()
        else:
            self._in_memory = False
            self.db_path = db_path or _DEFAULT_DB_PATH
            self._conn = None

    def rebuild(self, signatures: List[ClassSignature], source_hashes: Optional[dict] = None) -> int:
        """Full rebuild of the Deep Index.

        Args:
            signatures: List of ClassSignature to store
            source_hashes: Optional dict {file_path: sha256} for file-level tracking

        Returns:
            Number of classes indexed
        """
        conn = self._connect()
        try:
            conn.execute(_SCHEMA_TABLE)
            for idx_sql in _SCHEMA_INDEXES:
                conn.execute(idx_sql)
            conn.execute("DELETE FROM class_signatures")

            count = 0
            for sig in signatures:
                uid = f"{sig.file_path}::{sig.class_name}"
                source_hash = (source_hashes or {}).get(sig.file_path, "")
                conn.execute(
                    """INSERT INTO class_signatures
                       (uid, file_path, class_name, source_hash,
                        explicit_attrs, property_attrs, method_names,
                        observation_scope, scanned_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (
                        uid, sig.file_path, sig.class_name, source_hash,
                        json.dumps(sig.explicit_attrs),
                        json.dumps(sig.property_attrs),
                        json.dumps(sig.method_names),
                        sig.observation_scope,
                    ),
                )
                count += 1

            conn.commit()
            return count
        finally:
            if not self._in_memory:
                conn.close()

    def lookup_class(self, file_path: str, class_name: str) -> Optional[ClassSignature]:
        """Look up a ClassSignature by file_path and class_name.

        Returns:
            ClassSignature or None if not found
        """
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT file_path, class_name, explicit_attrs, property_attrs,
                          method_names, observation_scope
                   FROM class_signatures
                   WHERE file_path = ? AND class_name = ?""",
                (file_path, class_name),
            ).fetchone()

            if not row:
                return None

            return _row_to_signature(row)
        finally:
            if not self._in_memory:
                conn.close()

    def lookup_file(self, file_path: str) -> List[ClassSignature]:
        """Get all ClassSignatures for a file."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT file_path, class_name, explicit_attrs, property_attrs,
                          method_names, observation_scope
                   FROM class_signatures
                   WHERE file_path = ?""",
                (file_path,),
            ).fetchall()

            return [_row_to_signature(row) for row in rows]
        finally:
            if not self._in_memory:
                conn.close()

    def get_all_signatures(self) -> List[ClassSignature]:
        """Get all ClassSignatures in the index."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT file_path, class_name, explicit_attrs, property_attrs,
                          method_names, observation_scope
                   FROM class_signatures"""
            ).fetchall()

            return [_row_to_signature(row) for row in rows]
        finally:
            if not self._in_memory:
                conn.close()

    def class_count(self) -> int:
        """Total number of classes indexed."""
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM class_signatures").fetchone()
            return row[0]
        finally:
            if not self._in_memory:
                conn.close()

    def _connect(self) -> sqlite3.Connection:
        """Return a connection — reuses shared conn for in-memory mode."""
        if self._in_memory and self._conn is not None:
            return self._conn
        return self._new_connection()

    def _new_connection(self) -> sqlite3.Connection:
        """Create a fresh SQLite connection with row factory."""
        db_path = _resolve_db_path(self.db_path)
        conn = sqlite3.connect(db_path, uri=self._in_memory)
        conn.row_factory = sqlite3.Row
        return conn

    def close(self):
        """Close the in-memory connection if held."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _resolve_db_path(db_path: str) -> str:
    """Resolve db_path, creating parent directories if persisted."""
    if db_path == ":memory:" or db_path.startswith("file:"):
        return db_path
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)
