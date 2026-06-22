"""DuckDB-native Phase 1 processor.

Replaces the per-symbol Python BFS with SQL-based graph traversal
for massive speedup on large codebases.

Key optimization: instead of per-node SQLite round-trips (connect +
query + close) for each BFS step, all graph data is loaded into
DuckDB temp tables, and the BFS (depth <= 3) is computed via
iterative frontier-expansion in SQL with strict visited-set pruning.

IMPORTANT: Uses frontier-based expansion (not full self-joins) to
avoid combinatorial explosion.  At each depth level, only the NEW
unvisited nodes form the frontier for the next step.

@module quro.tda.phase1.duckdb_processor
@intent Push Phase 1 BFS traversal into DuckDB SQL for massive speedup
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

import duckdb


class DuckDBPhase1Processor:
    """Phase 1 processor that computes BFS traversal entirely in DuckDB SQL.

    Invariants:
      - Reads graph data ONCE from registry.db (SQLite) into DuckDB temp tables
      - Performs all graph traversal in SQL (no per-node Python/SQLite round-trips)
      - Generates events with proper JSON payloads matching the Pydantic schema
      - Bulk-inserts events via executemany

    Expected speedup: ~50-100x over the per-symbol Python BFS approach.
    """

    def __init__(
        self,
        registry_db: Path,
        db_path: Path,
        tau: float = 0.05,
        max_depth: int = 3,
        incremental: bool = False,
        duckdb_threads: Optional[int] = None,
        duckdb_memory_limit: Optional[str] = None,
    ):
        if tau < 0:
            raise ValueError(f"tau must be >= 0, got {tau}")
        if max_depth < 1:
            raise ValueError(f"max_depth must be >= 1, got {max_depth}")

        self.registry_db = registry_db
        self.db_path = db_path
        self.tau = tau
        self.max_depth = max_depth
        self.incremental = incremental
        self.duckdb_threads = duckdb_threads
        self.duckdb_memory_limit = duckdb_memory_limit
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def run(self) -> int:
        """Run Phase 1 using DuckDB-native traversal.

        Returns:
            Total number of events written.
        """
        if self.incremental:
            # TODO: support incremental mode by filtering symbols already
            # present in the events table.  For now, raise to avoid silently
            # doing a full traversal when the user expects incremental.
            raise NotImplementedError(
                "Incremental mode is not yet supported for DuckDB Phase 1"
            )

        print("[Phase-1-DuckDB] Connecting to DuckDB...")
        self._conn = duckdb.connect(str(self.db_path))
        if self.duckdb_threads is not None:
            self._conn.execute(f"SET threads={int(self.duckdb_threads)}")
        if self.duckdb_memory_limit is not None:
            self._conn.execute(f"SET memory_limit='{self.duckdb_memory_limit}'")
        self._conn.execute("SET preserve_insertion_order=false")
        self._conn.execute("SET temp_directory='/tmp'")

        try:
            print("[Phase-1-DuckDB] Loading graph data from registry.db...")
            self._load_graph_data()

            print("[Phase-1-DuckDB] Computing BFS paths in SQL...")
            self._compute_bfs_paths()

            print("[Phase-1-DuckDB] Building events...")
            total = self._build_and_insert_events()

            print(f"[Phase-1-DuckDB] Complete: {total} events written")
            return total
        finally:
            if self._conn:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------
    # Step 1: Load SQLite data into DuckDB temp tables
    # ------------------------------------------------------------------

    def _load_graph_data(self) -> None:
        """Load all nodes and edges from registry.db into DuckDB temp tables."""
        sqlite_conn = sqlite3.connect(str(self.registry_db))
        sqlite_conn.row_factory = sqlite3.Row

        try:
            # --- Load nodes ---
            cursor = sqlite_conn.execute(
                "SELECT id, type, tags, metadata FROM nodes"
            )
            # Consider: ATTACH 'registry.db' (TYPE sqlite) to DuckDB directly,
            # or batch-fetch to avoid loading all rows into Python memory.
            rows = cursor.fetchall()
            print(f"[Phase-1-DuckDB]   Loaded {len(rows)} nodes from registry")

            self._conn.execute("""
                CREATE OR REPLACE TEMP TABLE _nodes (
                    id      TEXT PRIMARY KEY,
                    type    TEXT NOT NULL,
                    tags    TEXT,
                    metadata TEXT
                )
            """)

            self._conn.executemany(
                "INSERT INTO _nodes VALUES (?, ?, ?, ?)",
                [
                    (r["id"], r["type"], r["tags"] or "", r["metadata"] or "{}")
                    for r in rows
                ],
            )

            # --- Load edges ---
            cursor = sqlite_conn.execute(
                "SELECT src, dst, weight, kind FROM edges"
            )
            rows = cursor.fetchall()
            print(f"[Phase-1-DuckDB]   Loaded {len(rows)} edges from registry")

            self._conn.execute("""
                CREATE OR REPLACE TEMP TABLE _edges (
                    src     TEXT NOT NULL,
                    dst     TEXT NOT NULL,
                    weight  DOUBLE NOT NULL,
                    kind    TEXT NOT NULL
                )
            """)

            self._conn.executemany(
                "INSERT INTO _edges VALUES (?, ?, ?, ?)",
                [
                    (r["src"], r["dst"], r["weight"], r["kind"])
                    for r in rows
                ],
            )

            # Indexes for join performance
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS _idx_edges_src ON _edges(src)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS _idx_edges_dst ON _edges(dst)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS _idx_nodes_type ON _nodes(type)"
            )

        finally:
            sqlite_conn.close()

    # ------------------------------------------------------------------
    # Step 2: Frontier-based iterative BFS (avoids combinatorial explosion)
    # ------------------------------------------------------------------

    def _compute_bfs_paths(self) -> None:
        """Compute all reachable nodes using frontier-expansion BFS.

        CRITICAL: Uses strict frontier-based expansion, NOT full self-joins.
        At each depth, only NEW unvisited nodes form the frontier for the
        next step.  This prevents the O(N^d) combinatorial explosion that
        occurs when self-joining ALL paths.

        Algorithm (per depth level):
          1. Find ALL outgoing edges from current frontier nodes
             → these become EDGE_TRAVERSE events
          2. Among those edges, find targets NOT already visited
             → these become the NEXT frontier and NODE_VISIT events

        Creates temp tables:
          _symbols       — BFS start symbols
          _visited       — (start_id, node_id, depth) visited set
          _edge_events   — all edge traversals
          _queries       — query_id per start symbol
        """
        tau = self.tau
        max_depth = self.max_depth

        # Symbols that serve as BFS start nodes
        self._conn.execute("""
            CREATE OR REPLACE TEMP TABLE _symbols AS
            SELECT id FROM _nodes WHERE type = 'symbol'
        """)

        symbol_count = self._conn.execute(
            "SELECT COUNT(*) FROM _symbols"
        ).fetchone()[0]
        print(f"[Phase-1-DuckDB]   {symbol_count} start symbols")

        # Visited set: (start_id, node_id, depth)
        # Initialize with all start symbols at depth 0
        self._conn.execute("""
            CREATE OR REPLACE TEMP TABLE _visited AS
            SELECT id AS start_id, id AS node_id, 0 AS depth
            FROM _symbols
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS _idx_visited_lookup "
            "ON _visited(start_id, node_id)"
        )

        # Edge events accumulator: union of edges from all frontier levels
        self._conn.execute("""
            CREATE OR REPLACE TEMP TABLE _edge_events (
                start_id    TEXT NOT NULL,
                src         TEXT NOT NULL,
                dst         TEXT NOT NULL,
                edge_type   TEXT NOT NULL,
                weight      DOUBLE NOT NULL,
                edge_depth  INTEGER NOT NULL
            )
        """)

        # --- Iterative BFS ---
        for d in range(max_depth):
            # Current frontier: nodes at depth `d`
            edge_depth = d  # edge traversed from a node at depth d

            # 1. Find all outgoing edges from the current frontier
            self._conn.execute(
                """
                INSERT INTO _edge_events (start_id, src, dst, edge_type, weight, edge_depth)
                SELECT
                    v.start_id,
                    v.node_id AS src,
                    e.dst,
                    e.kind,
                    e.weight,
                    ? AS edge_depth
                FROM _visited v
                JOIN _edges e ON v.node_id = e.src AND e.weight >= ?
                WHERE v.depth = ?
                """,
                [edge_depth, tau, d],
            )

            edge_rows = self._conn.execute(
                "SELECT COUNT(*) FROM _edge_events WHERE edge_depth = ?",
                [edge_depth],
            ).fetchone()[0]
            print(f"[Phase-1-DuckDB]   Depth-{d} edges: {edge_rows}")

            if d + 1 > max_depth:
                break

            # 2. Find NEW unvisited targets → these form the depth-(d+1) frontier
            self._conn.execute(
                """
                INSERT INTO _visited (start_id, node_id, depth)
                SELECT DISTINCT ee.start_id, ee.dst, ?
                FROM _edge_events ee
                WHERE ee.edge_depth = ?
                  AND NOT EXISTS (
                    SELECT 1 FROM _visited v
                    WHERE v.start_id = ee.start_id AND v.node_id = ee.dst
                  )
                """,
                [d + 1, edge_depth],
            )

            new_count = self._conn.execute(
                "SELECT COUNT(*) FROM _visited WHERE depth = ?",
                [d + 1],
            ).fetchone()[0]
            print(f"[Phase-1-DuckDB]   Depth-{d + 1} new nodes: {new_count}")

            if new_count == 0:
                print(f"[Phase-1-DuckDB]   BFS converged at depth {d + 1}")
                break

        # Summary
        total_edges = self._conn.execute(
            "SELECT COUNT(*) FROM _edge_events"
        ).fetchone()[0]
        total_visits = self._conn.execute(
            "SELECT COUNT(*) FROM _visited"
        ).fetchone()[0]
        print(f"[Phase-1-DuckDB]   Total edge traversals: {total_edges}")
        print(f"[Phase-1-DuckDB]   Total node visits: {total_visits}")

        # --- Assign query_ids to symbols ---
        self._conn.execute("""
            CREATE OR REPLACE TEMP TABLE _queries AS
            SELECT id AS symbol_id, gen_random_uuid()::TEXT AS query_id
            FROM _symbols
        """)

    # ------------------------------------------------------------------
    # Step 3: Build event dicts and bulk-insert into events table
    # ------------------------------------------------------------------

    def _build_and_insert_events(self) -> int:
        """Build event payloads and bulk-insert into the events table.

        Key optimization: NODE_VISIT and EDGE_TRAVERSE events are generated
        via pure SQL INSERT ... SELECT, eliminating Python-side serialization
        and per-row UUID/json.dumps() overhead for millions of rows.
        QUERY_METADATA (~3k rows) remains in Python.
        """
        total = 0
        timestamp = int(time.time() * 1e6)
        tau = self.tau
        max_depth = self.max_depth

        self._conn.execute("BEGIN TRANSACTION")
        try:
            # --- QUERY_METADATA events (~3k, Python is fine) ---
            print("[Phase-1-DuckDB]   Inserting QUERY_METADATA events...")
            queries = self._conn.execute(
                "SELECT symbol_id, query_id FROM _queries"
            ).fetchall()

            query_events = []
            for symbol_id, query_id in queries:
                event = {
                    "record_type": "QUERY_METADATA",
                    "query_id": query_id,
                    "timestamp": timestamp,
                    "query_params": {
                        "start": symbol_id,
                        "target": None,
                        "tau": tau,
                        "max_depth": max_depth,
                        "mode": "offline_batch",
                    },
                    "execution_stats": {
                        "duration_ms": None,
                        "nodes_visited": None,
                        "edges_traversed": None,
                    },
                }
                query_events.append(self._make_event_row(
                    event_id=str(uuid.uuid4()),
                    query_id=query_id,
                    timestamp=timestamp,
                    event_type="QUERY_METADATA",
                    src=symbol_id,
                    dst=None,
                    weight=None,
                    depth=0,
                    payload=event,
                ))

            _BATCH = 5000
            for i in range(0, len(query_events), _BATCH):
                self._conn.executemany(
                    "INSERT OR IGNORE INTO events "
                    "(event_id, query_id, timestamp, event_type, "
                    "src, dst, weight, depth, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    query_events[i : i + _BATCH],
                )
            total += len(query_events)
            print(f"[Phase-1-DuckDB]     {len(query_events)} query metadata events")

            # --- NODE_VISIT events: pure SQL INSERT ... SELECT ---
            # Eliminates Python fetchall() + per-row dict construction +
            # json.dumps() for 867k rows.  Metadata comes from _nodes via LEFT JOIN.
            print("[Phase-1-DuckDB]   Inserting NODE_VISIT events...")
            self._conn.execute("""
                INSERT OR IGNORE INTO events
                    (event_id, query_id, timestamp, event_type,
                     src, dst, weight, depth, payload)
                SELECT
                    gen_random_uuid()::TEXT,
                    q.query_id,
                    $timestamp,
                    'NODE_VISIT',
                    v.node_id,
                    NULL,
                    NULL,
                    v.depth,
                    (json_object(
                        'event_type', 'NODE_VISIT',
                        'event_id', gen_random_uuid()::TEXT,
                        'timestamp', $timestamp,
                        'query_id', q.query_id,
                        'node', json_object(
                            'id', v.node_id,
                            'kind', COALESCE(
                                CASE WHEN json_valid(n.metadata)
                                     THEN n.metadata->>'$.kind'
                                     ELSE NULL END,
                                'unknown'
                            ),
                            'file_path', COALESCE(
                                n.metadata->>'$.file_path',
                                ''
                            ),
                            'line_number', COALESCE(
                                (n.metadata->>'$.line')::INTEGER,
                                0
                            ),
                            'signature', n.metadata->>'$.signature'
                        ),
                        'visit_context', json_object(
                            'depth', v.depth,
                            'predecessor', NULL,
                            'via_edge_type', NULL
                        )
                    ))::TEXT
                FROM _visited v
                JOIN _queries q ON v.start_id = q.symbol_id
                LEFT JOIN _nodes n ON v.node_id = n.id
            """, {"timestamp": timestamp})

            node_count = self._conn.execute(
                "SELECT COUNT(*) FROM _visited"
            ).fetchone()[0]
            total += node_count
            print(f"[Phase-1-DuckDB]     {node_count} node visit events")

            # --- EDGE_TRAVERSE events: pure SQL INSERT ... SELECT ---
            # This is the 9.2M-row bottleneck.  Replaces Python fetchall() +
            # per-row uuid.uuid4() + json.dumps() + executemany batches with a
            # single streaming INSERT ... SELECT.  DuckDB's columnar pipeline
            # handles JSON construction natively, eliminating the Python GIL.
            print("[Phase-1-DuckDB]   Inserting EDGE_TRAVERSE events...")
            self._conn.execute("""
                INSERT OR IGNORE INTO events
                    (event_id, query_id, timestamp, event_type,
                     src, dst, weight, depth, payload)
                SELECT
                    gen_random_uuid()::TEXT,
                    q.query_id,
                    $timestamp,
                    'EDGE_TRAVERSE',
                    ee.src,
                    ee.dst,
                    ee.weight,
                    ee.edge_depth,
                    (json_object(
                        'event_type', 'EDGE_TRAVERSE',
                        'event_id', gen_random_uuid()::TEXT,
                        'timestamp', $timestamp,
                        'query_id', q.query_id,
                        'edge', json_object(
                            'src', ee.src,
                            'dst', ee.dst,
                            'edge_type', ee.edge_type,
                            'weight', ee.weight,
                            'direction', 'outbound'
                        ),
                        'traverse_context', json_object(
                            'depth', ee.edge_depth,
                            'tau_threshold', $tau,
                            'passed_gate',
                                CASE WHEN ee.weight >= $tau THEN true ELSE false END
                        )
                    ))::TEXT
                FROM _edge_events ee
                JOIN _queries q ON ee.start_id = q.symbol_id
            """, {"timestamp": timestamp, "tau": tau})

            edge_count = self._conn.execute(
                "SELECT COUNT(*) FROM _edge_events"
            ).fetchone()[0]
            total += edge_count
            print(f"[Phase-1-DuckDB]     {edge_count} edge traverse events")

            self._conn.execute("COMMIT")
            return total
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_event_row(
        event_id: str,
        query_id: str,
        timestamp: int,
        event_type: str,
        src: Optional[str],
        dst: Optional[str],
        weight: Optional[float],
        depth: Optional[int],
        payload: dict,
    ) -> tuple:
        """Build a tuple for INSERT into the events table."""
        return (
            event_id,
            query_id,
            timestamp,
            event_type,
            src,
            dst,
            weight,
            depth,
            json.dumps(payload),
        )
