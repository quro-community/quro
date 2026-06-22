"""TdaSchema — Declarative DDL definitions for DuckDB storage.

@module quro.storage.schema
@intent Define DDL for all DuckDB tables; track schema version
@role Policy (declarative rules, no I/O, no runtime logic)
"""

from typing import List, Tuple

__all__ = ["TdaSchema"]


class TdaSchema:
    """Immutable DDL definitions and version tracking for quro_tda.duckdb.

    Tables are organized by pipeline phase:
      - v1: Phase 1 events + imported nodes/edges + Phase 2 manifold
      - v2: Phase 2.5 energy/anisotropic fields + adjacency + meta

    Invariants:
      - Each method returns raw SQL strings, never executes them
      - Schema definitions are immutable per version
      - Migrations track ordered upgrade paths
    """

    CURRENT_VERSION: int = 2

    @staticmethod
    def v1_tables() -> List[Tuple[str, str]]:
        """Phase 1 + Phase 1.5 + Phase 2 table DDL.

        Returns:
            List of (table_name, create_sql) tuples.
        """
        return [
            ("events", """
                CREATE TABLE IF NOT EXISTS events (
                    event_id     TEXT PRIMARY KEY,
                    query_id     TEXT NOT NULL,
                    timestamp    BIGINT NOT NULL,
                    event_type   TEXT NOT NULL,
                    src          TEXT,
                    dst          TEXT,
                    weight       DOUBLE,
                    depth        INTEGER,
                    payload      TEXT
                )
            """),
            ("nodes", """
                CREATE TABLE IF NOT EXISTS nodes (
                    id           TEXT PRIMARY KEY,
                    type         TEXT NOT NULL,
                    tags         TEXT[],
                    metadata     JSON
                )
            """),
            ("edges_weighted", """
                CREATE TABLE IF NOT EXISTS edges_weighted (
                    from_id      TEXT NOT NULL,
                    to_id        TEXT NOT NULL,
                    weight       DOUBLE NOT NULL,
                    kind         TEXT NOT NULL,
                    friction     DOUBLE DEFAULT 1.0,
                    PRIMARY KEY (from_id, to_id)
                )
            """),
            ("manifold_states", """
                CREATE TABLE IF NOT EXISTS manifold_states (
                    symbol_id           TEXT PRIMARY KEY,
                    embedding           DOUBLE[5],
                    centrality          DOUBLE,
                    betweenness         DOUBLE,
                    clustering_coeff    DOUBLE,
                    tau_persistence     DOUBLE,
                    entry_variance      DOUBLE,
                    structural_noise    DOUBLE,
                    role_type           TEXT,
                    role_confidence     DOUBLE,
                    frequency           INTEGER,
                    burstiness          DOUBLE,
                    first_seen          BIGINT
                )
            """),
        ]

    @staticmethod
    def v2_tables() -> List[Tuple[str, str]]:
        """Phase 2.5 + coordination table DDL.

        Returns:
            List of (table_name, create_sql) tuples.
        """
        return [
            ("_meta", """
                CREATE TABLE IF NOT EXISTS _meta (
                    key    TEXT PRIMARY KEY,
                    value  TEXT NOT NULL
                )
            """),
            ("energy_states", """
                CREATE TABLE IF NOT EXISTS energy_states (
                    symbol_id           TEXT PRIMARY KEY,
                    potential           DOUBLE,
                    structural_gravity  DOUBLE,
                    entropy_bonus       DOUBLE,
                    energy_total        DOUBLE,
                    friction            DOUBLE,
                    mass                DOUBLE,
                    field_magnitude     DOUBLE,
                    field_direction     DOUBLE[3],
                    field_role          TEXT
                )
            """),
            ("anisotropic_fields", """
                CREATE TABLE IF NOT EXISTS anisotropic_fields (
                    symbol_id           TEXT PRIMARY KEY,
                    forward_direction   DOUBLE[3],
                    forward_magnitude   DOUBLE,
                    backward_tension    DOUBLE,
                    source_diversity    DOUBLE,
                    in_degree           INTEGER,
                    out_degree          INTEGER
                )
            """),
            ("adjacency", """
                CREATE TABLE IF NOT EXISTS adjacency (
                    from_id     TEXT NOT NULL,
                    to_id       TEXT NOT NULL,
                    PRIMARY KEY (from_id, to_id)
                )
            """),
            ("phase_completion", """
                CREATE TABLE IF NOT EXISTS phase_completion (
                    phase        TEXT PRIMARY KEY,
                    status       TEXT NOT NULL,
                    started_at   TIMESTAMP,
                    completed_at TIMESTAMP,
                    row_count    INTEGER,
                    data_hash    TEXT
                )
            """),
            ("semantic_centers", """
                CREATE TABLE IF NOT EXISTS semantic_centers (
                    center_id       TEXT PRIMARY KEY,
                    center_size     INTEGER,
                    archetype       TEXT,
                    connected_to    TEXT[],
                    geometry        JSON,
                    basin_symbols   INTEGER,
                    coverage        DOUBLE
                )
            """),
        ]

    @staticmethod
    def all_tables() -> List[Tuple[str, str]]:
        """Combined DDL for all tables (v1 + v2)."""
        return TdaSchema.v1_tables() + TdaSchema.v2_tables()

    @staticmethod
    def migrations() -> List[Tuple[int, int, str]]:
        """Ordered migration steps.

        Returns:
            List of (from_version, to_version, sql) tuples.
            Migrations are append-only and run in a single transaction.
        """
        # Future migration examples:
        # Migration V1→V2: add new tables introduced in v2
        v1_to_v2_sql = ";\n".join(
            sql.strip() for _, sql in TdaSchema.v2_tables()
        )
        return [
            (1, 2, v1_to_v2_sql),
        ]

    @staticmethod
    def version_sql() -> str:
        """SQL to read current schema version from _meta."""
        return "SELECT value FROM _meta WHERE key = 'schema_version'"

    @staticmethod
    def set_version_sql(version: int) -> str:
        """SQL to upsert schema version into _meta."""
        return (
            "INSERT OR REPLACE INTO _meta (key, value) "
            f"VALUES ('schema_version', '{version}')"
        )
