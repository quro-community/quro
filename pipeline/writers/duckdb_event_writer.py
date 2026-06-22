"""DuckDB Event Writer

@module quro.pipeline.writers.duckdb_event_writer
@intent Append graph traversal events to DuckDB events table during Phase 1
@role Extension (I/O-bound, no computation)
"""

import json
import logging
from typing import List, Dict, Any

import duckdb

logger = logging.getLogger(__name__)

__all__ = ["DuckDBEventWriter"]

DEFAULT_BATCH_SIZE = 1000


class DuckDBEventWriter:
    """Streaming event writer for Phase 1 pipeline.

    Inserts events into DuckDB's `events` table in batches.
    Uses INSERT OR IGNORE for idempotent writes (dedup by event_id).

    Invariants:
      - INSERT-only (never UPDATE or DELETE)
      - Batched writes (default 1000 events per flush)
      - Never closes the shared connection
      - Must not batch indefinitely (auto-flush at batch_size)

    Lifecycle:
      - Created at Phase 1 start
      - flush() called periodically during traversal
      - close() flushes remaining and releases connection reference
    """

    def __init__(
        self,
        connection: duckdb.DuckDBPyConnection,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        """Initialize event writer.

        Args:
            connection: Active DuckDB connection
            batch_size: Events to buffer before flushing (default: 1000)
        """
        self._conn = connection
        self._batch_size = batch_size
        self._buffer: List[Dict[str, Any]] = []
        self._total_written = 0

    def write_event(self, event: Dict[str, Any]) -> None:
        """Buffer and optionally flush an event.

        Args:
            event: Event dict from Phase 1 schema classes.
        """
        self._buffer.append(event)
        if len(self._buffer) >= self._batch_size:
            self.flush()

    def flush(self) -> int:
        """Commit all buffered events to DuckDB via bulk executemany.

        Returns:
            Number of events written in this flush.

        Note:
            Falls back to individual inserts if bulk insert fails.
        """
        if not self._buffer:
            return 0

        rows = []
        for event in self._buffer:
            event_id = event.get("event_id", "")
            query_id = event.get("query_id", "")
            timestamp = event.get("timestamp", 0)
            event_type = event.get("event_type", "")

            src = None
            dst = None
            weight = None
            depth = None

            if event_type == "NODE_VISIT":
                node_info = event.get("node", {})
                visit_ctx = event.get("visit_context", {})
                src = node_info.get("id", "")
                depth = visit_ctx.get("depth")
            elif event_type == "EDGE_TRAVERSE":
                edge_info = event.get("edge", {})
                traverse_ctx = event.get("traverse_context", {})
                src = edge_info.get("src", "")
                dst = edge_info.get("dst", "")
                weight = edge_info.get("weight")
                depth = traverse_ctx.get("depth")
            elif event_type == "PATH_COMPLETE":
                path_ctx = event.get("path_context", {})
                src = path_ctx.get("entry_point", "")
                dst = path_ctx.get("target", "")

            payload = json.dumps(event)
            rows.append((
                event_id,
                query_id,
                timestamp,
                event_type,
                src,
                dst,
                weight,
                depth,
                payload,
            ))

        try:
            self._conn.execute("BEGIN TRANSACTION")
            self._conn.executemany(
                "INSERT OR IGNORE INTO events "
                "(event_id, query_id, timestamp, event_type, "
                "src, dst, weight, depth, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            self._conn.execute("COMMIT")
            count = len(rows)
        except Exception:
            try:
                self._conn.execute("ROLLBACK")
            except Exception:
                logger.exception("ROLLBACK failed")
            logger.exception("Bulk insert failed, falling back to individual inserts")
            count = 0
            for row in rows:
                try:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO events "
                        "(event_id, query_id, timestamp, event_type, "
                        "src, dst, weight, depth, payload) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        row,
                    )
                    count += 1
                except Exception as exc:
                    logger.warning(
                        "Skipping row due to error: event_id=%s, error=%s",
                        row[0], exc,
                    )
                    continue

        self._total_written += count
        self._buffer.clear()
        logger.debug("Flushed %d events (total: %d)", count, self._total_written)
        return count

    def close(self) -> None:
        """Flush remaining buffer and release connection reference."""
        self.flush()
        logger.info("DuckDBEventWriter closed: %d events written", self._total_written)
        self._conn = None

    @property
    def total_written(self) -> int:
        """Total events written since creation."""
        return self._total_written
