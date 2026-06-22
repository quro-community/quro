"""
Phase-2 Main Orchestrator

Coordinates the three-pass pipeline.
"""

import pickle
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from .pass1_distill import AtomicFeatureDistiller
from .pass2_topology import TopologyInferenceEngine
from .pass3_project import SemanticProjector


class Phase2Orchestrator:
    """Orchestrates the three-pass Phase-2 pipeline."""

    def __init__(
        self,
        events_path: Path,
        output_path: Path,
        duckdb_conn = None,
    ):
        self.events_path = events_path
        self.output_path = output_path
        self.duckdb_conn = duckdb_conn

    def run(self) -> None:
        """Run the complete Phase-2 pipeline."""
        start_time = datetime.now()
        print(f"[Phase-2] Starting manifold inference pipeline...")
        print(f"[Phase-2] Input: {self.events_path}")
        print(f"[Phase-2] Output: {self.output_path}")
        print()

        # Pass 1: Atomic Feature Distillation
        print("=" * 60)
        print("PASS 1: ATOMIC FEATURE DISTILLATION")
        print("=" * 60)
        distiller = AtomicFeatureDistiller(self.events_path)
        if self.duckdb_conn is not None:
            self._distill_from_duckdb(distiller)
        else:
            distiller.distill()
        print()
        print("Pass 1 Statistics:")
        for key, value in distiller.get_statistics().items():
            print(f"  {key}: {value}")
        print()

        # Pass 2: Topology Inference
        print("=" * 60)
        print("PASS 2: TOPOLOGY INFERENCE")
        print("=" * 60)
        topology = TopologyInferenceEngine(
            adjacency=distiller.adjacency,
            frequency=distiller.frequency,
            tau_survival=distiller.tau_survival,
            edge_types=distiller.edge_types,
        )
        topology.infer()
        print()
        print("Pass 2 Statistics:")
        for key, value in topology.get_statistics().items():
            print(f"  {key}: {value}")
        print()

        # Pass 3: Semantic Projection
        print("=" * 60)
        print("PASS 3: SEMANTIC PROJECTION")
        print("=" * 60)
        projector = SemanticProjector(
            adjacency=distiller.adjacency,
            frequency=distiller.frequency,
            tau_survival=distiller.tau_survival,
            edge_types=distiller.edge_types,
            topology=topology,
        )
        projector.project(self.output_path)
        print()
        print("Pass 3 Statistics:")
        for key, value in projector.get_statistics().items():
            print(f"  {key}: {value}")
        print()

        # Pass 4: Field Enrichment
        print("=" * 60)
        print("PASS 4: FIELD ENRICHMENT (Phase 2 + Phase 2.5 Merge)")
        print("=" * 60)
        from .pass4_field_enrichment import enrich_with_field_metrics
        from .schema import SymbolManifoldState
        import json

        # Load manifold states
        manifold_states = []
        with open(self.output_path) as f:
            for line in f:
                data = json.loads(line)
                sms = SymbolManifoldState(**data)
                manifold_states.append(sms)

        # Enrich with Phase 2 field metrics (basic)
        enriched_states = enrich_with_field_metrics(manifold_states)

        print(f"Phase 2 enrichment: {len(enriched_states)} symbols")
        print()

        # Pass 4.5: Offline Physics Integration (Phase 2.5)
        print("=" * 60)
        print("PASS 4.5: OFFLINE PHYSICS INTEGRATION (Phase 2.5)")
        print("=" * 60)

        # Get workspace root from output path
        # output_path is: workspace/.quro_context/tda/phase2/manifold_states.jsonl
        # Resolve to absolute path first, then go up 4 levels to workspace root
        abs_output_path = self.output_path.resolve()
        workspace_root = abs_output_path.parent.parent.parent.parent
        offline_energy_path = workspace_root / ".quro_context" / "tda" / "phase2_5" / "offline_energy.json"

        if offline_energy_path.exists():
            print(f"Loading offline physics from: {offline_energy_path}")

            with open(offline_energy_path) as f:
                offline_data = json.load(f)

            offline_states = offline_data.get("states", {})
            merged_count = 0

            # Merge offline physics into manifold states
            for sms in enriched_states:
                symbol_id = sms.symbol
                if symbol_id in offline_states:
                    offline_state = offline_states[symbol_id]

                    # Replace energy with offline physics (new format)
                    # New format has: potential, structural_gravity, entropy_bonus, total
                    # Old format had: potential, kinetic, total
                    if "structural_gravity" in offline_state:
                        # New physics-based format (Design 85)
                        sms.energy = {
                            "potential": offline_state["potential"],
                            "structural_gravity": offline_state["structural_gravity"],
                            "entropy_bonus": offline_state["entropy_bonus"],
                            "total": offline_state["total"],
                        }
                    else:
                        # Legacy format (backward compatibility)
                        sms.energy = {
                            "potential": offline_state["potential"],
                            "kinetic": offline_state.get("kinetic", 0.0),
                            "total": offline_state["total"],
                        }

                    # Replace field role with offline classification
                    sms.field_role = offline_state["field_role"]

                    # Replace field magnitude with offline gradient
                    sms.field_magnitude = offline_state["field_magnitude"]

                    # Keep mass and friction from offline physics
                    sms.mass = offline_state["mass"]
                    sms.friction = offline_state["friction"]

                    merged_count += 1

            print(f"Merged offline physics for {merged_count}/{len(enriched_states)} symbols")

            # Statistics
            attractors = sum(1 for s in enriched_states if s.field_role == "attractor")
            repellers = sum(1 for s in enriched_states if s.field_role == "repeller")
            saddle_points = sum(1 for s in enriched_states if s.field_role == "saddle_point")

            print(f"  Attractors: {attractors} ({attractors/len(enriched_states)*100:.1f}%)")
            print(f"  Repellers: {repellers} ({repellers/len(enriched_states)*100:.1f}%)")
            print(f"  Saddle points: {saddle_points} ({saddle_points/len(enriched_states)*100:.1f}%)")
        else:
            print(f"Offline physics not found at: {offline_energy_path}")
            print("Run Phase 2.5 first: python -m quro.tda.phase2_5")
            print("Continuing with Phase 2 field enrichment only...")

        print()

        # Write back
        with open(self.output_path, 'w') as f:
            for sms in enriched_states:
                f.write(sms.model_dump_json() + '\n')

        print(f"Final output: {len(enriched_states)} symbols with complete field metrics")
        print()

        # Save adjacency cache for downstream phases (Phase 3.6, Phase 4, etc.)
        # This avoids re-parsing graph_events.jsonl (20GB) in later phases
        print("=" * 60)
        print("SAVING ADJACENCY CACHE")
        print("=" * 60)
        self._save_adjacency_cache(distiller, self.output_path)

        # Write manifold states to DuckDB if available
        if self.duckdb_conn is not None:
            self._write_manifold_to_duckdb(enriched_states)

        # Summary
        duration = (datetime.now() - start_time).total_seconds()
        print("=" * 60)
        print("PHASE-2 COMPLETE")
        print("=" * 60)
        print(f"Duration: {duration:.2f} seconds")
        print(f"Output: {self.output_path}")
        print()

    def _distill_from_duckdb(self, distiller: AtomicFeatureDistiller) -> None:
        """Read events from DuckDB and pass to distiller."""
        import json

        print("[Phase-2] Reading events from DuckDB...")
        rows = self.duckdb_conn.execute(
            "SELECT event_id, query_id, timestamp, event_type, "
            "src, dst, weight, depth, payload FROM events"
        ).fetchall()

        events = []
        for row in rows:
            payload = row[8]
            if payload:
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
            else:
                event = {
                    "event_id": row[0],
                    "query_id": row[1],
                    "timestamp": row[2],
                    "event_type": row[3],
                    "src": row[4],
                    "dst": row[5],
                    "weight": row[6],
                    "depth": row[7],
                }
            events.append(event)

        distiller.distill_from_events(events)

    def _write_manifold_to_duckdb(self, enriched_states: list) -> None:
        """Write manifold states to DuckDB."""
        count = 0
        for sms in enriched_states:
            embedding = sms.manifold_position.embedding if sms.manifold_position else [0.0] * 5
            energy = sms.energy or {}
            self.duckdb_conn.execute(
                "INSERT OR REPLACE INTO manifold_states "
                "(symbol_id, embedding, centrality, betweenness, "
                "clustering_coeff, tau_persistence, entry_variance, "
                "structural_noise, role_type, role_confidence, "
                "frequency, burstiness, first_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sms.symbol,
                    embedding,
                    sms.topology.centrality,
                    sms.topology.betweenness,
                    sms.topology.clustering_coeff,
                    sms.stability.tau_persistence,
                    sms.stability.entry_variance,
                    sms.stability.structural_noise,
                    sms.role.type,
                    sms.role.confidence,
                    sms.temporal_signature.frequency,
                    sms.temporal_signature.burstiness,
                    sms.temporal_signature.first_seen,
                ),
            )
            count += 1
        print(f"[Phase-2] Written {count} manifold states to DuckDB")

    def _save_adjacency_cache(self, distiller: AtomicFeatureDistiller, output_path: Path) -> None:
        """Save adjacency matrix as adjacency_cache.pkl for downstream phases.

        This cache is consumed by:
        - Phase 3.6 (Center Detection)
        - Phase 4 (Trajectory Planning)
        - MCP Server

        Without this cache, these phases would need to re-parse graph_events.jsonl (20GB).
        """
        # Resolve path to get workspace root
        abs_output = Path(output_path).resolve()
        tda_root = abs_output.parent.parent  # phase2/ -> tda/

        cache_path = tda_root / "adjacency_cache.pkl"

        # Convert SparseAdjacencyMatrix to plain dicts
        adjacency_dict = {}
        for src, dst_weights in distiller.adjacency.matrix.items():
            adjacency_dict[src] = list(dst_weights.keys())

        in_matrix_dict = {}
        for dst, src_weights in distiller.adjacency.in_matrix.items():
            in_matrix_dict[dst] = list(src_weights.keys())

        num_nodes = len(adjacency_dict)
        num_edges = sum(len(v) for v in adjacency_dict.values())

        cache_data = {
            "version": "1.0",
            "adjacency": adjacency_dict,  # forward: src -> [dsts]
            "in_matrix": in_matrix_dict,   # reverse: dst -> [srcs]
            "metadata": {
                "num_nodes": num_nodes,
                "num_edges": num_edges,
                "created_at": datetime.utcnow().isoformat(),
                "source": "graph_events.jsonl",
                "phase": "phase2",
                "description": (
                    "Adjacency cache created by Phase 2. "
                    "Use this instead of re-parsing graph_events.jsonl."
                ),
            }
        }

        with open(cache_path, 'wb') as f:
            pickle.dump(cache_data, f)

        print(f"Adjacency cache saved: {cache_path}")
        print(f"  Nodes: {num_nodes}")
        print(f"  Edges: {num_edges}")

        # Also write adjacency to DuckDB if available
        if self.duckdb_conn is not None:
            count = 0
            for src, dst_list in adjacency_dict.items():
                for dst in dst_list:
                    self.duckdb_conn.execute(
                        "INSERT OR IGNORE INTO adjacency (from_id, to_id) "
                        "VALUES (?, ?)",
                        (src, dst),
                    )
                    count += 1
            print(f"  DuckDB adjacency edges: {count}")

        print()


def main():
    """CLI entry point."""
    # Default paths
    workspace_root = Path.cwd()
    events_path = workspace_root / ".quro_context" / "tda" / "phase1" / "graph_events.jsonl"
    output_path = workspace_root / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"

    # Check if events file exists
    if not events_path.exists():
        print(f"[Phase-2] Error: Phase-1 events not found: {events_path}", file=sys.stderr)
        print(f"[Phase-2] Run Phase-1 first: python -m quro.tda.phase1", file=sys.stderr)
        sys.exit(1)

    # Run pipeline
    orchestrator = Phase2Orchestrator(events_path, output_path)
    orchestrator.run()


if __name__ == "__main__":
    main()
