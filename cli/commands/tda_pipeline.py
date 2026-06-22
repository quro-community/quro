"""TDA Pipeline Commands

@module quro.cli.commands.tda_pipeline
@intent CLI commands for TDA data pipeline execution.

The TDA pipeline consists of multiple phases that build upon each other:

Phase 1: Graph Event Collection
  - Collects CQE traversal events from the symbol graph
  - Observes semantic relationships and co-occurrence patterns
  - Output: quro_tda.duckdb (events table) or graph_events.jsonl

Phase 2: Manifold Inference
  - Distills atomic features from graph events
  - Infers topological structure
  - Projects symbols onto semantic manifold
  - Output: quro_tda.duckdb (manifold_states, adjacency tables) or manifold_states.jsonl

Phase 2.5: Static Physics Enrichment
  - Extracts git heat (change frequency)
  - Analyzes structural metrics (gravity, mass, friction)
  - Computes asymmetric edge weights
  - Initializes energy field
  - Computes anisotropic fields (forward/backward tension)
  - Applies attractor bias
  - Output: quro_tda.duckdb (energy_states, anisotropic_fields tables) or JSON files

Phase 3.5: Holographic Field Construction
  - Aggregates symbol fields into spatial grid
  - Maps manifold fields (gradients, curvature)
  - Assembles codebase hologram
  - Output: quro_tda.duckdb (semantic_centers table) or JSON files

Phase 3.6: Semantic Center Detection
  - Detects attractor basins (semantic centers)
  - Builds inter-center graph
  - Output: semantic_centers.json

Phase 4: Trajectory Planning
  - Loads field data for navigation
  - Enables A* planning and beam search
  - Output: Cached in memory for fast queries
"""

import argparse
import sys
from pathlib import Path

from cli.base import BaseCommand


class TDAPipelineCommand(BaseCommand):
    """Run TDA data pipeline phases."""

    def get_name(self) -> str:
        return "tda pipeline"

    def get_help(self) -> str:
        return "Run TDA data pipeline phases"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "phase",
            choices=["1", "2", "2.5", "3.5", "3.6", "all"],
            help=(
                "Pipeline phase to run:\n"
                "  1    - Graph event collection (CQE traversal)\n"
                "  2    - Manifold inference (topology + projection)\n"
                "  2.5  - Static physics enrichment (energy fields)\n"
                "  3.5  - Holographic field construction\n"
                "  3.6  - Semantic center detection\n"
                "  all  - Run all phases sequentially"
            ),
        )
        parser.add_argument(
            "--backend",
            choices=["jsonl", "duckdb"],
            default="duckdb",
            help=(
                "Storage backend for TDA data (default: duckdb):\n"
                "  duckdb - Write all data to quro_tda.duckdb (unified storage)\n"
                "  jsonl  - Write events to JSONL files"
            ),
        )
        parser.add_argument(
            "--workspace",
            type=Path,
            default=Path.cwd(),
            help="Workspace root directory (default: current directory)",
        )
        parser.add_argument(
            "--incremental",
            action="store_true",
            help="[Phase 1 only] Skip already-processed symbols",
        )
        parser.add_argument(
            "--tau",
            type=float,
            default=0.05,
            help="[Phase 1 only] MI-gate threshold (default: 0.05)",
        )
        parser.add_argument(
            "--max-depth",
            type=int,
            default=3,
            help="[Phase 1 only] Maximum BFS depth (default: 3)",
        )

    def execute(self, args: argparse.Namespace) -> int:
        workspace = args.workspace.resolve()
        backend = getattr(args, "backend", "duckdb")

        if args.phase == "all":
            return self._run_all_phases(workspace, args, backend)
        elif args.phase == "1":
            return self._run_phase1(workspace, args, backend)
        elif args.phase == "2":
            return self._run_phase2(workspace, backend)
        elif args.phase == "2.5":
            return self._run_phase2_5(workspace, backend)
        elif args.phase == "3.5":
            return self._run_phase3_5(workspace, backend)
        elif args.phase == "3.6":
            return self._run_phase3_6(workspace)

        return 1

    def _run_all_phases(self, workspace: Path, args: argparse.Namespace,
                        backend: str) -> int:
        """Run all phases sequentially."""
        print("=" * 60)
        print("TDA PIPELINE: RUNNING ALL PHASES")
        print(f"  Backend: {backend}")
        print("=" * 60)
        print()

        phases = [
            ("Phase 1: Graph Event Collection", lambda: self._run_phase1(workspace, args, backend)),
            ("Phase 2: Manifold Inference", lambda: self._run_phase2(workspace, backend)),
            ("Phase 2.5: Static Physics Enrichment", lambda: self._run_phase2_5(workspace, backend)),
            ("Phase 2.5+: Populate Energy Fields in Registry", lambda: self._run_populate_fields(workspace)),
            ("Phase 3.5: Holographic Field Construction", lambda: self._run_phase3_5(workspace, backend)),
            ("Phase 3.6: Semantic Center Detection", lambda: self._run_phase3_6(workspace)),
        ]

        for phase_name, phase_func in phases:
            print(f"\n{'=' * 60}")
            print(phase_name)
            print('=' * 60)
            result = phase_func()
            if result != 0:
                print(f"\n[Error] {phase_name} failed", file=sys.stderr)
                return result

        print("\n" + "=" * 60)
        print("TDA PIPELINE: ALL PHASES COMPLETE")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  - Query TDA: quro tda plan sym::A sym::B")
        print("  - Generate visualizations: quro visualize all")
        print()

        return 0

    def _run_phase1(self, workspace: Path, args: argparse.Namespace,
                    backend: str = "duckdb") -> int:
        """Run Phase 1: Graph Event Collection."""
        import time

        registry_db = workspace / ".quro_context" / "registry.db"

        if not registry_db.exists():
            print(f"[Error] Registry database not found: {registry_db}", file=sys.stderr)
            print("[Hint] Run: quro scan", file=sys.stderr)
            return 1

        db_path = workspace / ".quro_context" / "quro_tda.duckdb"

        if backend == "duckdb":
            # Ensure DuckDB schema is initialized before processor opens it
            # (MigrationRunner only creates tables; no open connection to close)
            from storage.coordinator import StorageCoordinator
            StorageCoordinator(db_path).ensure_initialized()

            from tda.phase1.duckdb_processor import DuckDBPhase1Processor

            output_label = str(db_path)
        else:
            output_path = workspace / ".quro_context" / "tda" / "phase1" / "graph_events.jsonl"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_label = str(output_path)

        print("[Phase 1] Graph Event Collection")
        print(f"  Backend: {backend}")
        print(f"  Registry: {registry_db}")
        print(f"  Output: {output_label}")
        print(f"  Tau: {args.tau}, Max Depth: {args.max_depth}")
        print(f"  Incremental: {args.incremental}")
        print()

        start_time = time.time()

        if backend == "duckdb":
            processor = DuckDBPhase1Processor(
                registry_db=registry_db,
                db_path=db_path,
                tau=args.tau,
                max_depth=args.max_depth,
                incremental=args.incremental,
            )
            try:
                total_events = processor.run()
            except NotImplementedError as e:
                print(f"\n[Error] {e}", file=sys.stderr)
                return 1
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"\n[Error] {e}", file=sys.stderr)
                return 1
            print(f"[Phase 1] Events written to DuckDB: {total_events}")
        else:
            import asyncio
            from tda.phase1.batch_processor import Phase1BatchProcessor

            processor = Phase1BatchProcessor(
                registry_db=registry_db,
                output_path=output_path,
                tau=args.tau,
                max_depth=args.max_depth,
                duckdb_writer=None,
            )
            try:
                asyncio.run(processor.run_full_traversal(incremental=args.incremental))
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"\n[Error] {e}", file=sys.stderr)
                return 1

        duration = time.time() - start_time
        print(f"\n[Phase 1] Duration: {int(duration // 60)}m {int(duration % 60)}s")
        print("[Phase 1] ✓ Complete")
        return 0

    def _run_phase2(self, workspace: Path, backend: str = "duckdb") -> int:
        """Run Phase 2: Manifold Inference."""
        from tda.phase2.__main__ import Phase2Orchestrator

        events_path = workspace / ".quro_context" / "tda" / "phase1" / "graph_events.jsonl"
        output_path = workspace / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"
        db_path = workspace / ".quro_context" / "quro_tda.duckdb"

        duckdb_conn = None
        coordinator = None

        if backend == "duckdb":
            from storage.coordinator import StorageCoordinator

            if not db_path.exists():
                print(f"[Error] DuckDB not found: {db_path}", file=sys.stderr)
                print("[Hint] Run: quro tda pipeline 1 --backend duckdb", file=sys.stderr)
                return 1

            coordinator = StorageCoordinator(db_path)
            duckdb_conn = coordinator.open()
            print(f"[Phase 2] Using DuckDB events from: {db_path}")
        else:
            if not events_path.exists():
                print(f"[Error] Phase 1 events not found: {events_path}", file=sys.stderr)
                print("[Hint] Run: quro tda pipeline 1", file=sys.stderr)
                return 1
            print(f"[Phase 2] Using JSONL events from: {events_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        orchestrator = Phase2Orchestrator(
            events_path, output_path, duckdb_conn=duckdb_conn,
        )
        try:
            orchestrator.run()
        except Exception as e:
            print(f"\n[Error] {e}", file=sys.stderr)
            return 1
        finally:
            if coordinator is not None:
                coordinator.close()

        return 0

    def _run_phase2_5(self, workspace: Path, backend: str = "duckdb") -> int:
        """Run Phase 2.5: Static Physics Enrichment."""
        from tda.phase2_5.__main__ import run_phase2_5

        print(f"[Phase 2.5] Backend: {backend}")

        try:
            result = run_phase2_5(workspace)

            if backend == "duckdb" and result == 0:
                self._write_energy_to_duckdb(workspace)

            return result
        except Exception as e:
            print(f"\n[Error] {e}", file=sys.stderr)
            return 1

    def _write_energy_to_duckdb(self, workspace: Path) -> None:
        """Write Phase 2.5 energy data into DuckDB tables."""
        import json
        from storage.coordinator import StorageCoordinator

        energy_path = workspace / ".quro_context" / "tda" / "phase2_5" / "offline_energy.json"
        anisotropic_path = workspace / ".quro_context" / "tda" / "phase2_5" / "anisotropic_fields.jsonl"
        db_path = workspace / ".quro_context" / "quro_tda.duckdb"

        try:
            coordinator = StorageCoordinator(db_path)
            conn = coordinator.open()

            # Import energy states
            if energy_path.exists():
                with open(energy_path, "r") as f:
                    data = json.load(f)
                states = data.get("states", {})
                count = 0
                for symbol_id, state in states.items():
                    field_dir = state.get("field_direction")
                    fd = [float(v) for v in field_dir] if field_dir and len(field_dir) == 3 else [0.0, 0.0, 0.0]
                    conn.execute(
                        "INSERT OR REPLACE INTO energy_states "
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
                print(f"[Phase 2.5] Written {count} energy states to DuckDB")

            # Import anisotropic fields
            if anisotropic_path.exists():
                acount = 0
                with open(anisotropic_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        field = json.loads(line)
                        conn.execute(
                            "INSERT OR REPLACE INTO anisotropic_fields "
                            "(symbol_id, forward_direction, forward_magnitude, "
                            "backward_tension, source_diversity, "
                            "in_degree, out_degree) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                field.get("symbol_id", ""),
                                field.get("forward_direction"),
                                field.get("forward_magnitude"),
                                field.get("backward_tension"),
                                field.get("source_diversity"),
                                field.get("in_degree"),
                                field.get("out_degree"),
                            ),
                        )
                        acount += 1
                print(f"[Phase 2.5] Written {acount} anisotropic fields to DuckDB")

            coordinator.close()
        except Exception as e:
            print(f"[Phase 2.5] Warning: Failed to write energy to DuckDB: {e}",
                  file=sys.stderr)

    def _run_phase3_5(self, workspace: Path, backend: str = "duckdb") -> int:
        """Run Phase 3.5: Holographic Field Construction."""
        from tda.phase3_5.__main__ import Phase35Orchestrator

        manifold_states_path = workspace / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"
        output_path = workspace / ".quro_context" / "tda" / "phase3_5" / "codebase_hologram.json"
        centers_output_path = workspace / ".quro_context" / "tda" / "phase3_5" / "semantic_centers.json"

        if not manifold_states_path.exists():
            print(f"[Error] Phase 2 manifold states not found: {manifold_states_path}", file=sys.stderr)
            print("[Hint] Run: quro tda pipeline 2", file=sys.stderr)
            return 1

        print(f"[Phase 3.5] Backend: {backend}")

        orchestrator = Phase35Orchestrator(manifold_states_path, output_path, centers_output_path)
        try:
            orchestrator.run()
        except Exception as e:
            print(f"\n[Error] {e}", file=sys.stderr)
            return 1

        if backend == "duckdb":
            self._write_centers_to_duckdb(workspace)

        return 0

    def _write_centers_to_duckdb(self, workspace: Path) -> None:
        """Write semantic centers into DuckDB."""
        import json
        from storage.coordinator import StorageCoordinator

        centers_path = workspace / ".quro_context" / "tda" / "phase3_5" / "semantic_centers.json"
        db_path = workspace / ".quro_context" / "quro_tda.duckdb"

        if not centers_path.exists():
            return

        try:
            coordinator = StorageCoordinator(db_path)
            conn = coordinator.open()

            with open(centers_path, "r") as f:
                data = json.load(f)

            centers = data.get("centers", [])
            count = 0
            for center in centers:
                topology = center.get("topology", {})
                conn.execute(
                    "INSERT OR REPLACE INTO semantic_centers "
                    "(center_id, center_size, archetype, connected_to, "
                    "geometry, basin_symbols, coverage) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        center.get("id", ""),
                        center.get("size", 0),
                        topology.get("pattern", ""),
                        topology.get("connected_centers", []),
                        json.dumps(center.get("geometry", {})),
                        center.get("size", 0),
                        center.get("coverage", 0.0),
                    ),
                )
                count += 1

            print(f"[Phase 3.5] Written {count} semantic centers to DuckDB")
            coordinator.close()
        except Exception as e:
            print(f"[Phase 3.5] Warning: Failed to write centers to DuckDB: {e}",
                  file=sys.stderr)

    def _run_phase3_6(self, workspace: Path) -> int:
        """Run Phase 3.6: Semantic Center Detection (standalone)."""
        # Phase 3.6 is now integrated into Phase 3.5
        print("[Phase 3.6] Semantic center detection is integrated into Phase 3.5")
        print("[Hint] Run: quro tda pipeline 3.5")
        return 0

    def _run_populate_fields(self, workspace: Path) -> int:
        """Run populate energy fields (Phase 2.5+)."""
        import json
        import sqlite3

        registry_db = workspace / ".quro_context" / "registry.db"
        offline_energy_path = workspace / ".quro_context" / "tda" / "phase2_5" / "offline_energy.json"

        if not registry_db.exists():
            print(f"[Warning] Registry database not found: {registry_db}", file=sys.stderr)
            print("[Info] Skipping energy field population", file=sys.stderr)
            return 0

        if not offline_energy_path.exists():
            print(f"[Warning] Offline energy data not found: {offline_energy_path}", file=sys.stderr)
            print("[Info] Skipping energy field population", file=sys.stderr)
            return 0

        print("[Phase 2.5+] Populating energy fields in registry database")
        print(f"  Registry: {registry_db}")
        print(f"  Energy data: {offline_energy_path}")
        print()

        try:
            # Load offline energy data
            with open(offline_energy_path) as f:
                energy_data = json.load(f)

            states = energy_data.get("states", {})

            if not states:
                print("[Warning] No energy states found in offline_energy.json", file=sys.stderr)
                return 0

            print(f"Loaded {len(states)} energy states")

            # Update registry database
            conn = sqlite3.connect(registry_db)
            cursor = conn.cursor()

            # Check if columns exist
            cursor.execute("PRAGMA table_info(nodes)")
            columns = {row[1] for row in cursor.fetchall()}

            required_columns = ["energy_total", "field_role", "field_magnitude", "mass", "friction"]
            missing_columns = [col for col in required_columns if col not in columns]

            if missing_columns:
                print(f"[Info] Missing columns in nodes table: {missing_columns}", file=sys.stderr)
                print("[Info] Running migration to add columns...", file=sys.stderr)
                conn.close()
                try:
                    conn = sqlite3.connect(registry_db)
                    cursor = conn.cursor()
                    for col_name, col_type in [
                        ("energy_total", "REAL"),
                        ("field_role", "TEXT"),
                        ("field_magnitude", "REAL"),
                        ("mass", "REAL"),
                        ("friction", "REAL"),
                    ]:
                        if col_name not in columns:
                            cursor.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_type}")
                            print(f"  [Migration] Added column: {col_name}", file=sys.stderr)
                    conn.commit()
                    conn.close()
                    conn = sqlite3.connect(registry_db)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(nodes)")
                    columns = {row[1] for row in cursor.fetchall()}
                    missing_columns = [col for col in required_columns if col not in columns]
                    if missing_columns:
                        print("[Error] Migration failed to add columns", file=sys.stderr)
                        return 1
                    print("[OK] Migration complete, continuing...", file=sys.stderr)
                except Exception as e:
                    print(f"[Error] Migration error: {e}", file=sys.stderr)
                    return 1

            # Update nodes
            updated = 0
            for symbol_id, state in states.items():
                cursor.execute(
                    """
                    UPDATE nodes
                    SET energy_total = ?,
                        field_role = ?,
                        field_magnitude = ?,
                        mass = ?,
                        friction = ?
                    WHERE id = ?
                    """,
                    (
                        state["total"],
                        state["field_role"],
                        state["field_magnitude"],
                        state["mass"],
                        state["friction"],
                        symbol_id,
                    ),
                )
                if cursor.rowcount > 0:
                    updated += 1

            conn.commit()
            conn.close()

            print(f"[Phase 2.5+] Updated {updated}/{len(states)} symbols")
            print("[Phase 2.5+] ✓ Complete")

        except Exception as e:
            print(f"\n[Warning] Failed to populate energy fields: {e}", file=sys.stderr)
            print("[Info] Continuing with pipeline...", file=sys.stderr)
            return 0

        return 0


class TDAPopulateFieldsCommand(BaseCommand):
    """Populate TDA energy fields (migrate from scripts)."""

    def get_name(self) -> str:
        return "tda populate-fields"

    def get_help(self) -> str:
        return "Populate TDA energy fields in registry database"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--workspace",
            type=Path,
            default=Path.cwd(),
            help="Workspace root directory (default: current directory)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )

    def execute(self, args: argparse.Namespace) -> int:
        workspace = args.workspace.resolve()

        registry_db = workspace / ".quro_context" / "registry.db"
        offline_energy_path = workspace / ".quro_context" / "tda" / "phase2_5" / "offline_energy.json"

        if not registry_db.exists():
            print(f"[Error] Registry database not found: {registry_db}", file=sys.stderr)
            print("[Hint] Run: quro scan", file=sys.stderr)
            return 1

        if not offline_energy_path.exists():
            print(f"[Error] Offline energy data not found: {offline_energy_path}", file=sys.stderr)
            print("[Hint] Run: quro tda pipeline 2.5", file=sys.stderr)
            return 1

        print("[TDA] Populating energy fields in registry database")
        print(f"  Registry: {registry_db}")
        print(f"  Energy data: {offline_energy_path}")
        print(f"  Dry run: {args.dry_run}")
        print()

        try:
            # Import the logic from scripts/populate_tda_energy_fields.py
            import json
            import sqlite3

            # Load offline energy data
            with open(offline_energy_path) as f:
                energy_data = json.load(f)

            states = energy_data.get("states", {})

            if not states:
                print("[Error] No energy states found in offline_energy.json", file=sys.stderr)
                return 1

            print(f"Loaded {len(states)} energy states")

            if args.dry_run:
                print("\n[Dry Run] Would update the following symbols:")
                for symbol_id in list(states.keys())[:10]:
                    state = states[symbol_id]
                    print(f"  {symbol_id}: energy={state['total']:.2f}, role={state['field_role']}")
                if len(states) > 10:
                    print(f"  ... and {len(states) - 10} more")
                return 0

            # Update registry database
            conn = sqlite3.connect(registry_db)
            cursor = conn.cursor()

            # Check if columns exist
            cursor.execute("PRAGMA table_info(nodes)")
            columns = {row[1] for row in cursor.fetchall()}

            required_columns = ["energy_total", "field_role", "field_magnitude", "mass", "friction"]
            missing_columns = [col for col in required_columns if col not in columns]

            if missing_columns:
                print(f"[Info] Missing columns in nodes table: {missing_columns}", file=sys.stderr)
                print("[Info] Running migration to add columns...", file=sys.stderr)
                conn.close()
                try:
                    conn = sqlite3.connect(registry_db)
                    cursor = conn.cursor()
                    for col_name, col_type in [
                        ("energy_total", "REAL"),
                        ("field_role", "TEXT"),
                        ("field_magnitude", "REAL"),
                        ("mass", "REAL"),
                        ("friction", "REAL"),
                    ]:
                        if col_name not in columns:
                            cursor.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_type}")
                            print(f"  [Migration] Added column: {col_name}", file=sys.stderr)
                    conn.commit()
                    conn.close()
                    conn = sqlite3.connect(registry_db)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(nodes)")
                    columns = {row[1] for row in cursor.fetchall()}
                    missing_columns = [col for col in required_columns if col not in columns]
                    if missing_columns:
                        print("[Error] Migration failed to add columns", file=sys.stderr)
                        return 1
                    print("[OK] Migration complete, continuing...", file=sys.stderr)
                except Exception as e:
                    print(f"[Error] Migration error: {e}", file=sys.stderr)
                    return 1

            # Update nodes
            updated = 0
            for symbol_id, state in states.items():
                cursor.execute(
                    """
                    UPDATE nodes
                    SET energy_total = ?,
                        field_role = ?,
                        field_magnitude = ?,
                        mass = ?,
                        friction = ?
                    WHERE id = ?
                    """,
                    (
                        state["total"],
                        state["field_role"],
                        state["field_magnitude"],
                        state["mass"],
                        state["friction"],
                        symbol_id,
                    ),
                )
                if cursor.rowcount > 0:
                    updated += 1

            conn.commit()
            conn.close()

            print(f"\n[TDA] Updated {updated}/{len(states)} symbols")
            print("[TDA] ✓ Complete")

        except Exception as e:
            print(f"\n[Error] {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

        return 0
