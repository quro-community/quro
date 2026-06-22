"""MigrationRunner — Schema migration and data import orchestrator.

@module quro.storage.migration
@intent Detect schema version, run pending migrations, import legacy data
@role Orchestrator (migration coordination)
"""

import json
import logging
import pickle as pickle_module
from pathlib import Path
from typing import Optional

import duckdb

from storage.schema import TdaSchema

logger = logging.getLogger(__name__)

__all__ = ["MigrationRunner"]


class MigrationRunner:
    """Orchestrates DuckDB schema creation and legacy data import.

    Invariants:
      - All migrations run in a single DuckDB transaction
      - Rollback on any error
      - Version stored in _meta table
      - Never imports if DuckDB already has data for that source
    """

    def __init__(self, db_path: Path):
        """Initialize migration runner.

        Args:
            db_path: Path to quro_tda.duckdb
        """
        self.db_path = db_path
        self._version: Optional[int] = None

    def run(self) -> bool:
        """Detect version, apply pending migrations, import legacy data.

        Returns:
            True if migration succeeded (or was a no-op).
        """
        logger.info("MigrationRunner: checking schema at %s", self.db_path)

        try:
            conn = duckdb.connect(str(self.db_path))

            self._version = self._read_current_version(conn)

            if self._version == 0:
                self._initialize(conn)
            elif self._version < TdaSchema.CURRENT_VERSION:
                self._migrate(conn, self._version)

            self._import_legacy_data_if_empty(conn)

            conn.close()
            logger.info("MigrationRunner: complete (version %d)", TdaSchema.CURRENT_VERSION)
            return True

        except Exception:
            logger.exception("MigrationRunner: failed")
            return False

    def _read_current_version(self, conn: duckdb.DuckDBPyConnection) -> int:
        """Read schema version from _meta, or 0 if DB is empty."""
        try:
            result = conn.execute(
                "SELECT value FROM _meta WHERE key = 'schema_version'"
            ).fetchone()
            if result:
                return int(result[0])
        except Exception:
            pass
        return 0

    def _initialize(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create all tables from scratch."""
        logger.info("MigrationRunner: initializing new database")
        for table_name, ddl in TdaSchema.all_tables():
            conn.execute(ddl)
            logger.debug("  created table: %s", table_name)
        conn.execute(TdaSchema.set_version_sql(TdaSchema.CURRENT_VERSION))

    def _migrate(self, conn: duckdb.DuckDBPyConnection, from_version: int) -> None:
        """Apply pending migrations in order."""
        logger.info("MigrationRunner: migrating from version %d to %d",
                     from_version, TdaSchema.CURRENT_VERSION)
        for fv, tv, sql in TdaSchema.migrations():
            if fv >= from_version:
                logger.info("  applying migration: %d -> %d", fv, tv)
                conn.begin()
                try:
                    for statement in sql.split(";"):
                        statement = statement.strip()
                        if statement:
                            conn.execute(statement)
                    conn.execute(TdaSchema.set_version_sql(tv))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

    def _import_legacy_data_if_empty(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        """Import data from legacy JSONL/JSON/Pickle files if tables are empty.

        Scans for registry.db, graph_events.jsonl, manifold_states.jsonl,
        offline_energy.json, adjacency_cache.pkl in standard locations.
        """
        quro_context = self.db_path.parent

        self._import_nodes_from_registry(conn, quro_context)
        self._import_events_from_jsonl(conn, quro_context)
        self._import_manifold_from_jsonl(conn, quro_context)
        self._import_energy_from_json(conn, quro_context)
        self._import_adjacency_from_pkl(conn, quro_context)

    def _table_is_empty(self, conn: duckdb.DuckDBPyConnection, table: str) -> bool:
        """Check if a table has zero rows."""
        try:
            result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return result[0] == 0 if result else True
        except Exception:
            return True

    def _import_nodes_from_registry(
        self, conn: duckdb.DuckDBPyConnection, quro_context: Path
    ) -> None:
        """Import nodes from registry.db (SQLite)."""
        registry_db = quro_context / "registry.db"
        if not registry_db.exists():
            logger.debug("No registry.db found, skipping node import")
            return

        if not self._table_is_empty(conn, "nodes"):
            logger.debug("Nodes table not empty, skipping import")
            return

        logger.info("Importing nodes from registry.db ...")
        try:
            import sqlite3
            sqlite_conn = sqlite3.connect(str(registry_db))
            sqlite_conn.row_factory = sqlite3.Row
            cursor = sqlite_conn.execute(
                "SELECT id, type, tags, metadata FROM nodes"
            )
            rows = cursor.fetchall()
            count = 0
            for row in rows:
                tags_str = row["tags"] or ""
                metadata_str = row["metadata"] or "{}"
                tags_list = [
                    t.strip() for t in tags_str.split(",") if t.strip()
                ] if tags_str else []
                conn.execute(
                    "INSERT OR IGNORE INTO nodes (id, type, tags, metadata) "
                    "VALUES (?, ?, ?, ?)",
                    (row["id"], row["type"], tags_list, metadata_str),
                )
                count += 1
            sqlite_conn.close()
            logger.info("  imported %d nodes", count)
        except Exception:
            logger.exception("Failed to import nodes from registry.db")

    def _import_events_from_jsonl(
        self, conn: duckdb.DuckDBPyConnection, quro_context: Path
    ) -> None:
        """Import events from graph_events.jsonl."""
        events_path = quro_context / "tda" / "phase1" / "graph_events.jsonl"
        if not events_path.exists():
            logger.debug("No graph_events.jsonl found, skipping event import")
            return

        if not self._table_is_empty(conn, "events"):
            logger.debug("Events table not empty, skipping import")
            return

        logger.info("Importing events from graph_events.jsonl ...")
        count = 0
        skipped = 0
        try:
            with open(events_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
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

                        conn.execute(
                            "INSERT OR IGNORE INTO events "
                            "(event_id, query_id, timestamp, event_type, "
                            "src, dst, weight, depth, payload) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                event.get("event_id", ""),
                                event.get("query_id", ""),
                                event.get("timestamp", 0),
                                event_type,
                                src,
                                dst,
                                weight,
                                depth,
                                payload,
                            ),
                        )
                        count += 1
                    except (json.JSONDecodeError, Exception):
                        skipped += 1

            logger.info("  imported %d events (%d skipped)", count, skipped)
        except Exception:
            logger.exception("Failed to import events from graph_events.jsonl")

    def _import_manifold_from_jsonl(
        self, conn: duckdb.DuckDBPyConnection, quro_context: Path
    ) -> None:
        """Import manifold states from manifold_states.jsonl."""
        manifold_path = (
            quro_context / "tda" / "phase2" / "manifold_states.jsonl"
        )
        if not manifold_path.exists():
            logger.debug("No manifold_states.jsonl found, skipping import")
            return

        if not self._table_is_empty(conn, "manifold_states"):
            logger.debug("Manifold states table not empty, skipping import")
            return

        logger.info("Importing manifold states from manifold_states.jsonl ...")
        count = 0
        skipped = 0
        try:
            with open(manifold_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        embedding = data.get("embedding")
                        if embedding and len(embedding) == 5:
                            emb = [float(v) for v in embedding]
                        else:
                            emb = [0.0] * 5

                        conn.execute(
                            "INSERT OR IGNORE INTO manifold_states "
                            "(symbol_id, embedding, centrality, betweenness, "
                            "clustering_coeff, tau_persistence, entry_variance, "
                            "structural_noise, role_type, role_confidence, "
                            "frequency, burstiness, first_seen) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                data.get("symbol", data.get("symbol_id", "")),
                                emb,
                                data.get("centrality"),
                                data.get("betweenness"),
                                data.get("clustering_coeff"),
                                data.get("tau_persistence"),
                                data.get("entry_variance"),
                                data.get("structural_noise"),
                                data.get("role_type"),
                                data.get("role_confidence"),
                                data.get("frequency"),
                                data.get("burstiness"),
                                data.get("first_seen"),
                            ),
                        )
                        count += 1
                    except Exception:
                        skipped += 1

            logger.info("  imported %d manifold states (%d skipped)", count, skipped)
        except Exception:
            logger.exception("Failed to import manifold states")

    def _import_energy_from_json(
        self, conn: duckdb.DuckDBPyConnection, quro_context: Path
    ) -> None:
        """Import energy states from offline_energy.json."""
        energy_path = (
            quro_context / "tda" / "phase2_5" / "offline_energy.json"
        )
        if not energy_path.exists():
            logger.debug("No offline_energy.json found, skipping import")
            return

        if not self._table_is_empty(conn, "energy_states"):
            logger.debug("Energy states table not empty, skipping import")
            return

        logger.info("Importing energy states from offline_energy.json ...")
        count = 0
        try:
            with open(energy_path, "r") as f:
                data = json.load(f)

            states = data.get("states", {})
            for symbol_id, state in states.items():
                field_dir = state.get("field_direction")
                if field_dir and len(field_dir) == 3:
                    fd = [float(v) for v in field_dir]
                else:
                    fd = [0.0, 0.0, 0.0]

                conn.execute(
                    "INSERT OR IGNORE INTO energy_states "
                    "(symbol_id, potential, structural_gravity, "
                    "entropy_bonus, energy_total, friction, mass, "
                    "field_magnitude, field_direction, field_role) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        symbol_id,
                        state.get("potential"),
                        state.get("structural_gravity"),
                        state.get("entropy_bonus"),
                        state.get("total"),
                        state.get("friction"),
                        state.get("mass"),
                        state.get("field_magnitude"),
                        fd,
                        state.get("field_role"),
                    ),
                )
                count += 1

            logger.info("  imported %d energy states", count)
        except Exception:
            logger.exception("Failed to import energy states")

    def _import_adjacency_from_pkl(
        self, conn: duckdb.DuckDBPyConnection, quro_context: Path
    ) -> None:
        """Import adjacency from adjacency_cache.pkl."""
        pkl_path = quro_context / "tda" / "adjacency_cache.pkl"
        if not pkl_path.exists():
            logger.debug("No adjacency_cache.pkl found, skipping import")
            return

        if not self._table_is_empty(conn, "adjacency"):
            logger.debug("Adjacency table not empty, skipping import")
            return

        logger.info("Importing adjacency from adjacency_cache.pkl ...")
        count = 0
        try:
            with open(pkl_path, "rb") as f:
                cache_data = pickle_module.load(f)

            adjacency_dict = cache_data.get("adjacency", {})
            for src, dst_list in adjacency_dict.items():
                for dst in dst_list:
                    conn.execute(
                        "INSERT OR IGNORE INTO adjacency (from_id, to_id) "
                        "VALUES (?, ?)",
                        (src, dst),
                    )
                    count += 1

            logger.info("  imported %d adjacency edges", count)
        except Exception:
            logger.exception("Failed to import adjacency from pickle")

    @property
    def version(self) -> Optional[int]:
        """Current schema version after run()."""
        return self._version
