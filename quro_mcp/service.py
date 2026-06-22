"""Quro v3 MCP Service - Minimal Kernel

@module quro_mcp.service
@intent Expose v3 CQE as MCP tools
@constraint Stateless, on-demand execution
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import os
import uuid

from scanner.orchestrator import ScannerOrchestrator
from scanner.adapters.memory import MemoryAdapter as ScannerMemoryAdapter
from index_builder import IndexBuilder, MemoryRegistryAdapter
from index_builder.adapters.sqlite import SQLiteRegistryAdapter
from index_builder.types import EdgeWeightConfig, EnricherSpec, TypeBoundary
from index_builder.providers.default_enricher import DefaultHeuristicEnricher
from index_builder.enrichers import (
    HubPressureEnricher,
    PathEntropyEnricher,
    RoleEnricher,
    IntentEnricher,
)
from core.cqe.kernel import CQEKernel
from core.cqe.types import GraphProtocol, CQETier, CQEMultiTierResult
from core.cqe.refiner import DefaultCQERefiner, SemanticCQERefiner
from core.cqe.flow_observer import FlowObserver
from .tda_enricher import TDAFieldEnricher


class CQEGraphAdapter(GraphProtocol):
    """Adapter to make RegistryAdapter compatible with CQE GraphProtocol.

    Supports MI-adjusted edge weights via MorphismMIAdjuster.
    """

    def __init__(self, registry, mi_adjuster=None):
        self.registry = registry
        self.mi_adjuster = mi_adjuster

    def neighbors(self, node: str):
        """Yield (neighbor_node, edge_weight) tuples with MI adjustment and Top-K fanout pruning."""
        edges = list(self.registry.get_edges_from(node))

        # Apply MI adjustment if available (but exempt structural edges)
        if self.mi_adjuster:
            adjusted_edges = []
            for edge in edges:
                # Exempt CONTAINS edges from MI adjustment (structural, not execution)
                if edge.kind == "contains":
                    adjusted_weight = edge.weight
                else:
                    factor = self.mi_adjuster.compute_adjustment_factor(edge.src, edge.dst)
                    adjusted_weight = edge.weight * factor
                adjusted_edges.append((edge.dst, adjusted_weight))
        else:
            adjusted_edges = [(edge.dst, edge.weight) for edge in edges]

        # Apply Top-K fanout pruning if fanout > 12 (Design 90 recommendation)
        if len(adjusted_edges) > 12:
            # Sort by weight (higher = better transition)
            adjusted_edges.sort(key=lambda x: x[1], reverse=True)
            adjusted_edges = adjusted_edges[:10]  # Keep top 10

        # Yield (dst, weight) tuples
        for dst, weight in adjusted_edges:
            yield (dst, weight)

    def edges(self, node: str):
        """Yield GraphEdge objects for the node."""
        return self.registry.get_edges_from(node)

    def out_degree(self, node: str) -> int:
        """Get out-degree of node."""
        edges = self.registry.get_edges_from(node)
        return len(edges)


class QuroV3Service:
    """Minimal v3 kernel as MCP service.

    Provides:
    - scan_workspace: Scan workspace and build index
    - cqe_query: Semantic query over indexed graph
    - get_symbol: Get symbol details
    - get_stats: Get scan/index statistics
    """

    def __init__(self, workspace_root: Optional[Path] = None, enable_flow_trace: Optional[bool] = None):
        """Initialize service.

        Args:
            workspace_root: Workspace root directory (default: cwd)
            enable_flow_trace: Enable CQE flow tracing (default: from env QURO_FLOW_TRACE)
        """
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()

        # Flow observer (feature gate via env or param)
        if enable_flow_trace is None:
            enable_flow_trace = os.getenv("QURO_FLOW_TRACE", "false").lower() in ("true", "1", "yes")
        self.flow_observer = FlowObserver(enabled=enable_flow_trace)

        # Adapters
        self.scan_adapter = ScannerMemoryAdapter()

        # Try to load existing registry database, fallback to in-memory
        registry_db_path = self.workspace_root / ".quro_context" / "registry.db"
        if registry_db_path.exists():
            self.registry_adapter = SQLiteRegistryAdapter(db_path=registry_db_path)
        else:
            self.registry_adapter = MemoryRegistryAdapter()

        # Components
        self.scanner = ScannerOrchestrator(
            workspace_root=self.workspace_root,
            adapter=self.scan_adapter,
        )
        self.index_builder = IndexBuilder(
            adapter=self.registry_adapter,
            enrichers=[DefaultHeuristicEnricher()],
            edge_config=EdgeWeightConfig()
        )

        # Register Phase 1 enrichers
        self._register_phase1_enrichers()

        # Register Phase 2 enrichers
        self._register_phase2_enrichers()

        # Initialize MI adjuster (TDA + reflection history)
        self.mi_adjuster = None
        self._init_mi_adjuster()

        # CQE graph adapter (with MI adjustment)
        self.cqe_graph = CQEGraphAdapter(self.registry_adapter, self.mi_adjuster)

        # TDA field enricher
        self.tda_enricher = TDAFieldEnricher(workspace_root=self.workspace_root)

        # Upstream navigator (Phase 3.5)
        self.upstream_navigator = None
        self._init_upstream_navigator()

        # Statistics
        self.scan_stats = None
        self.build_stats = None

    def _init_mi_adjuster(self):
        """Initialize MI adjuster with TDA scores + reflection history."""
        # Import locally to avoid circular dependency
        from pipeline.cqe.mi_adjuster import MorphismMIAdjuster

        reflection_log_path = self.workspace_root / ".quro_context" / "cqe_reflections.jsonl"
        tda_scores_path = self.workspace_root / ".quro_context" / "tda_mi_scores.json"

        # Warn if neither source exists (MI adjustment silently skipped)
        if not reflection_log_path.exists() and not tda_scores_path.exists():
            print("Warning: No CQE reflection log or TDA scores found. "
                  "MI adjustment disabled. Run 'quro tda pipeline all' or "
                  "enable reflection logging to improve CQE quality.")

        # Only initialize if reflection log exists (graceful degradation)
        if reflection_log_path.exists():
            try:
                self.mi_adjuster, stats = MorphismMIAdjuster.from_reflection_log(
                    log_path=reflection_log_path,
                    tda_scores_path=tda_scores_path if tda_scores_path.exists() else None
                )
                print(f"MI Adjuster initialized: {stats['atoms_with_mi']} atoms from history, "
                      f"{stats.get('atoms_with_tda', 0)} from TDA")
            except Exception as e:
                print(f"Warning: Failed to initialize MI adjuster: {e}")
                self.mi_adjuster = None
        elif tda_scores_path.exists():
            # TDA-only mode (no reflection history yet)
            try:
                import json
                with open(tda_scores_path) as f:
                    tda_data = json.load(f)
                    tda_scores = {
                        atom_id: score_data["mi_score"]
                        for atom_id, score_data in tda_data.get("scores", {}).items()
                    }
                self.mi_adjuster = MorphismMIAdjuster({}, tda_scores)
                print(f"MI Adjuster initialized: TDA-only mode with {len(tda_scores)} atoms")
            except Exception as e:
                print(f"Warning: Failed to load TDA scores: {e}")
                self.mi_adjuster = None

    def _init_upstream_navigator(self):
        """Initialize upstream navigator if anisotropic fields exist."""
        from core.cqe.upstream_navigator import UpstreamNavigator

        anisotropic_fields_path = (
            self.workspace_root / ".quro_context" / "tda" / "phase2_5" / "anisotropic_fields.jsonl"
        )
        registry_db_path = self.workspace_root / ".quro_context" / "registry.db"

        if anisotropic_fields_path.exists() and registry_db_path.exists():
            try:
                self.upstream_navigator = UpstreamNavigator(
                    anisotropic_fields_path=anisotropic_fields_path,
                    registry_db_path=registry_db_path
                )
            except Exception as e:
                # Graceful degradation if upstream navigator fails to initialize
                print(f"Warning: Failed to initialize UpstreamNavigator: {e}")
                self.upstream_navigator = None

    def _register_phase1_enrichers(self):
        """Register Phase 1 semantic enrichers.

        Phase 1 includes:
        - PathEntropyEnricher: Detect noisy/ambiguous symbols
        - HubPressureEnricher: Detect high-fanout hubs (topology-aware)
        """
        # Build symbol registry for PathEntropyEnricher
        # (will be populated during indexing)
        symbol_registry = {}

        # Register PathEntropyEnricher (non-topology, priority 10)
        path_enricher = PathEntropyEnricher(symbol_registry, collision_threshold=1)
        self.index_builder.register_enricher(
            enricher=path_enricher,
            priority=10,
            spec=EnricherSpec(
                name="PathEntropyEnricher",
                input_boundary=TypeBoundary(),
                output_boundary=TypeBoundary(),
                description="Detect ambiguous symbols (name collisions, wildcard imports)",
            ),
        )

        # Register HubPressureEnricher (topology-aware, priority 100)
        hub_enricher = HubPressureEnricher(
            registry=self.registry_adapter,
            fanout_threshold=50,
        )
        self.index_builder.register_enricher(
            enricher=hub_enricher,
            priority=100,
            spec=EnricherSpec(
                name="HubPressureEnricher",
                input_boundary=TypeBoundary(),
                output_boundary=TypeBoundary(),
                description="Detect high-fanout hubs (>50 edges) for CQE pruning",
            ),
        )

    def _register_phase2_enrichers(self):
        """Register Phase 2 semantic enrichers.

        Phase 2 includes:
        - RoleEnricher: Detect architectural roles (controller, worker, etc.)
        - IntentEnricher: Detect semantic intent (io, network, database, etc.)
        """
        # Register RoleEnricher (non-topology, priority 20)
        role_enricher = RoleEnricher(confidence_threshold=0.3)
        self.index_builder.register_enricher(
            enricher=role_enricher,
            priority=20,
            spec=EnricherSpec(
                name="RoleEnricher",
                input_boundary=TypeBoundary(),
                output_boundary=TypeBoundary(),
                description="Detect architectural roles (controller, worker, adapter, etc.)",
            ),
        )

        # Register IntentEnricher (non-topology, priority 21)
        intent_enricher = IntentEnricher(confidence_threshold=0.3)
        self.index_builder.register_enricher(
            enricher=intent_enricher,
            priority=21,
            spec=EnricherSpec(
                name="IntentEnricher",
                input_boundary=TypeBoundary(),
                output_boundary=TypeBoundary(),
                description="Detect semantic intent (io, network, database, test, etc.)",
            ),
        )

    def scan_workspace(self, progress: bool = False) -> Dict[str, Any]:
        """Scan workspace and build index.

        Args:
            progress: Whether to show progress messages

        Returns:
            Dict with scan and build statistics
        """
        # Progress callback
        progress_callback = print if progress else None

        # Step 1: Scan workspace
        self.scanner.progress_callback = progress_callback
        self.scan_stats = self.scanner.scan_workspace()

        # Step 2: Build index
        symbols = self.scan_adapter.get_all_symbols()
        self.index_builder.progress_callback = progress_callback
        self.build_stats = self.index_builder.build_index(symbols)

        return {
            "scan": {
                "files_discovered": self.scan_stats.files_discovered,
                "files_scanned": self.scan_stats.files_scanned,
                "files_skipped": self.scan_stats.files_skipped,
                "symbols_found": self.scan_stats.symbols_found,
                "symbols_kept": self.scan_stats.symbols_kept,
                "symbols_filtered": self.scan_stats.symbols_filtered,
            },
            "index": {
                "symbols_indexed": self.build_stats.symbols_indexed,
                "nodes_created": self.build_stats.nodes_created,
                "edges_created": self.build_stats.edges_created,
                "categories_created": self.build_stats.categories_created,
            },
        }

    def cqe_query_with_mode(
        self,
        start: str,
        tau: float = 0.05,
        max_depth: int = 3,
        use_semantic_refiner: bool = True,
        traversal_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute CQE query with traversal mode support.

        Args:
            start: Starting node ID (e.g., "sym::LockManager" or "cat::async")
            tau: MI-gate threshold [0, 1]
            max_depth: Maximum traversal depth
            use_semantic_refiner: Use semantic refiner (default: True)
            traversal_mode: Force traversal mode (forward/reverse/field_guided/saddle_escape)

        Returns:
            Dict with query results (includes mode_switches and telemetry)
        """
        from core.cqe.traversal_orchestrator import TraversalOrchestrator
        from core.cqe.traversal_modes import TraversalMode
        from core.cqe.tda_bridge import TDABridge
        from adapters.graph.sqlite import SQLiteGraphAdapter
        import logging

        logger = logging.getLogger(__name__)

        # Load MI scores (empty for now, will be populated from reflection log)
        mi_scores = {}

        # Cold-start bypass: if no MI history, set tau=0 (graceful degradation)
        reflection_log = self.workspace_root / ".quro_context" / "cqe_reflections.jsonl"
        original_tau = tau
        if not reflection_log.exists() or reflection_log.stat().st_size == 0:
            logger.info("Cold-start detected: bypassing MI-gate (tau=0)")
            tau = 0.0

        # Initialize TDA bridge
        tda_bridge = TDABridge(self.workspace_root)

        # Get CQE index path
        cqe_index_path = self.workspace_root / ".quro_context" / "cqe_index.db"

        if not cqe_index_path.exists():
            return {
                "error": "CQE index not found. Run scan_workspace first.",
                "start": start,
            }

        # Resolve short symbol names to full IDs
        resolved_start = self._resolve_symbol_id(start, cqe_index_path)
        if resolved_start != start:
            # Symbol was resolved, use the full ID
            start = resolved_start

        # Parse traversal mode
        force_mode = None
        if traversal_mode:
            mode_map = {
                "forward": TraversalMode.FORWARD,
                "reverse": TraversalMode.REVERSE,
                "field_guided": TraversalMode.FIELD_GUIDED,
                "saddle_escape": TraversalMode.SADDLE_ESCAPE,
            }
            force_mode = mode_map.get(traversal_mode.lower())

        # Execute traversal with orchestrator
        with SQLiteGraphAdapter(cqe_index_path) as graph:
            orchestrator = TraversalOrchestrator(
                graph=graph,
                tda_bridge=tda_bridge,
                mi_scores=mi_scores,
            )

            result = orchestrator.traverse(
                start_node=start,
                max_depth=max_depth,
                top_k=10,
                force_mode=force_mode,
            )

            # Format results (convert NodeState to dict for JSON serialization)
            telemetry = dict(result.telemetry)
            if "node_state" in telemetry:
                node_state = telemetry["node_state"]
                telemetry["node_state"] = {
                    "node_id": node_state.node_id,
                    "out_degree": node_state.out_degree,
                    "in_degree": node_state.in_degree,
                    "node_role": node_state.node_role.value,
                    "field_role": node_state.field_role.value,
                    "gravity_score": node_state.gravity_score,
                    "energy_total": node_state.energy_total,
                    "field_magnitude": node_state.field_magnitude,
                }

            return {
                "start": start,
                "mode": result.mode.value,
                "visited_nodes": len(result.visited_nodes),
                "results": [
                    {
                        "node_id": node_id,
                        "score": score,
                        "path": path,
                    }
                    for node_id, score, path in result.results
                ],
                "mode_switches": [
                    {
                        "from_mode": event.from_mode.value,
                        "to_mode": event.to_mode.value,
                        "trigger": event.trigger,
                        "node_id": event.node_id,
                        "escape_probability": event.escape_probability,
                    }
                    for event in result.mode_switches
                ],
                "telemetry": telemetry,
                "fallback_used": "topology_cold_start" if tau != original_tau else None,
            }

    def _resolve_symbol_id(self, symbol_name: str, cqe_index_path: Path) -> str:
        """Resolve short symbol name to full ID.

        Args:
            symbol_name: Short name (e.g., 'sym::CQEIndexPipeline') or full ID
            cqe_index_path: Path to CQE index database

        Returns:
            Full symbol ID if found, otherwise original name
        """
        import sqlite3

        # If already a full ID (contains hash), return as-is
        if '::' in symbol_name:
            parts = symbol_name.split('::')
            # Check if last part looks like a hash (8+ hex chars)
            if len(parts) >= 3 and len(parts[-1]) >= 8:
                return symbol_name

        # Try to find matching symbol in database
        conn = sqlite3.connect(str(cqe_index_path))
        cursor = conn.cursor()

        # Extract the class/function name from short ID
        if symbol_name.startswith('sym::'):
            search_name = symbol_name.replace('sym::', '')
        elif symbol_name.startswith('cat::'):
            # Categories don't need resolution
            return symbol_name
        else:
            search_name = symbol_name

        # Search for symbols containing this name
        cursor.execute(
            "SELECT id FROM atoms WHERE id LIKE ? AND id LIKE 'sym::%' LIMIT 1",
            (f'%::{search_name}::%',)
        )
        result = cursor.fetchone()
        conn.close()

        if result:
            return result[0]

        # Not found, return original
        return symbol_name

    def cqe_query(
        self,
        start: str,
        tau: float = 0.05,
        max_depth: int = 3,
        use_semantic_refiner: bool = True,
        mi_weight: float = 0.1,
        use_soft_tau: bool = True,
    ) -> Dict[str, Any]:
        """Execute CQE semantic query with additive MI scoring (Design 93).

        Args:
            start: Starting node ID (e.g., "sym::LockManager" or "cat::async")
            tau: Soft threshold for ranking bias [0, 1]
            max_depth: Maximum traversal depth
            use_semantic_refiner: Use semantic refiner (default: True)
            mi_weight: Lambda coefficient for MI contribution (default: 0.1)
            use_soft_tau: Use soft tau (ranking) vs hard tau (gate) (default: True)

        Returns:
            Dict with query results (includes flow_trace if enabled)
        """
        from core.cqe.transforms import HubNormalizer, TopKPruner
        from core.cqe.refiner import DefaultCQERefiner
        import dataclasses

        # Start flow trace
        query_id = str(uuid.uuid4())
        trace = self.flow_observer.start_trace(query_id, {
            "start": start,
            "tau": tau,
            "max_depth": max_depth,
            "use_semantic_refiner": use_semantic_refiner,
            "mi_weight": mi_weight,
            "use_soft_tau": use_soft_tau,
        })

        # Transform graph
        transformed_graph = HubNormalizer.transform(self.cqe_graph)
        self.flow_observer.observe(query_id, "graph_transform_hub", transformed_graph, {
            "transform": "HubNormalizer"
        })

        transformed_graph = TopKPruner.transform(transformed_graph, max_edges=200)
        self.flow_observer.observe(query_id, "graph_transform_prune", transformed_graph, {
            "transform": "TopKPruner",
            "max_edges": 200
        })

        # Create MI scorer function if MI adjuster available
        mi_scorer = None
        if self.mi_adjuster:
            def mi_scorer(src: str, dst: str) -> float:
                mi_from = self.mi_adjuster.get_mi_score(src)
                mi_to = self.mi_adjuster.get_mi_score(dst)
                return (mi_from + mi_to) / 2.0

        # Execute CQE query with additive scoring (Design 93)
        result = CQEKernel.query(
            graph=transformed_graph,
            start=start,
            tau=tau,
            mi_weight=mi_weight,
            mi_scorer=mi_scorer,
            top_k=100,
            use_soft_tau=use_soft_tau,
        )
        self.flow_observer.observe(query_id, "kernel_output", result, {
            "path_count": len([w for w in result.max_weights.values() if w > 0])
        })

        # Fallback guarantee: if no results, retry with pure structural (mi_weight=0)
        if len(result.max_weights) <= 1 and mi_weight > 0:
            self.flow_observer.observe(query_id, "fallback_triggered", {
                "reason": "empty_results",
                "original_mi_weight": mi_weight
            })
            result = CQEKernel.query(
                graph=transformed_graph,
                start=start,
                tau=tau,
                mi_weight=0.0,  # Pure structural fallback
                mi_scorer=None,
                top_k=100,
                use_soft_tau=use_soft_tau,
            )
            self.flow_observer.observe(query_id, "fallback_result", result, {
                "path_count": len([w for w in result.max_weights.values() if w > 0])
            })

        def _fetch_node_metadata(node_id: str) -> Dict[str, Any]:
            node = self.registry_adapter.get_node(node_id)
            if not node:
                return {}
            return {
                "tags": list(node.tags),
                "metadata": node.metadata
            }

        def _fetch_aliases(node_id: str) -> List[Dict[str, str]]:
            """Fetch symbol aliases (duplicate implementations)."""
            aliases = self.registry_adapter.find_symbol_aliases(node_id)
            self.flow_observer.observe(query_id, f"alias_fetch_{node_id}", aliases, {
                "node_id": node_id,
                "alias_count": len(aliases)
            })
            return aliases

        # Choose refiner based on configuration
        refiner_type = "semantic" if use_semantic_refiner else "default"
        if use_semantic_refiner:
            refiner = SemanticCQERefiner(
                node_metadata_fetcher=_fetch_node_metadata,
                alias_fetcher=_fetch_aliases
            )
        else:
            refiner = DefaultCQERefiner(node_metadata_fetcher=_fetch_node_metadata)

        self.flow_observer.observe(query_id, "refiner_input", result)

        refined_result = refiner.refine(result=result, entry_token=start)
        self.flow_observer.observe(query_id, "refiner_output", refined_result, {
            "nodes_processed": refined_result.metadata.get("nodes_processed", 0),
            "truncated": refined_result.truncated
        })

        # Format results
        output = {
            "start": start,
            "tau": tau,
            "mi_weight": mi_weight,
            "use_soft_tau": use_soft_tau,
            "mode": refiner_type,
            "refined": dataclasses.asdict(refined_result),
            "max_weights": result.max_weights, # Keep for debugging
            "predecessors": result.predecessors, # Keep for debugging
            "path_count": len([w for w in result.max_weights.values() if w > 0]),
        }

        # Enrich with TDA field metrics
        output = self.tda_enricher.enrich_results(output)

        self.flow_observer.observe(query_id, "final_output", output)

        # Include flow trace if enabled
        if self.flow_observer.enabled:
            output["flow_trace"] = self.flow_observer.get_trace(query_id)
            self.flow_observer.clear_trace(query_id)  # Clean up

        return output

    def cqe_query_multi_tier(
        self,
        start: str,
        max_depth: int = 3,
        use_semantic_refiner: bool = True
    ) -> Dict[str, Any]:
        """Execute CQE query at multiple tau levels for tiered results.

        Returns results at 3 confidence levels:
        - core (tau=0.3): High confidence, tight focus
        - extended (tau=0.1): Medium confidence, balanced
        - exploratory (tau=0.05): Low confidence, wide discovery

        Args:
            start: Starting node ID (e.g., "sym::LockManager" or "cat::async")
            max_depth: Maximum traversal depth
            use_semantic_refiner: Use semantic refiner (default: True)

        Returns:
            Dict with multi-tier results
        """
        from core.cqe.transforms import HubNormalizer, TopKPruner
        import dataclasses

        transformed_graph = HubNormalizer.transform(self.cqe_graph)
        transformed_graph = TopKPruner.transform(transformed_graph, max_edges=200)

        def _fetch_node_metadata(node_id: str) -> Dict[str, Any]:
            node = self.registry_adapter.get_node(node_id)
            if not node:
                return {}
            return {
                "tags": list(node.tags),
                "metadata": node.metadata
            }

        def _fetch_aliases(node_id: str) -> List[Dict[str, str]]:
            """Fetch symbol aliases (duplicate implementations)."""
            return self.registry_adapter.find_symbol_aliases(node_id)

        # Run queries at 3 tau levels
        tau_levels = [
            (0.3, "core", "High-confidence core dependencies"),
            (0.1, "extended", "Medium-confidence related symbols"),
            (0.05, "exploratory", "Low-confidence peripheral connections"),
        ]

        tiers = {}
        for tau, tier_name, advisory in tau_levels:
            result = CQEKernel.query(
                graph=transformed_graph,
                start=start,
                tau=tau
            )

            # Choose refiner
            if use_semantic_refiner:
                refiner = SemanticCQERefiner(
                    node_metadata_fetcher=_fetch_node_metadata,
                    alias_fetcher=_fetch_aliases
                )
            else:
                refiner = DefaultCQERefiner(node_metadata_fetcher=_fetch_node_metadata)

            refined_result = refiner.refine(result=result, entry_token=start)

            tiers[tier_name] = {
                "tau": tau,
                "node_count": len(result.max_weights) - 1,  # Exclude entry token
                "refined": dataclasses.asdict(refined_result),
                "advisory": advisory,
            }

        # Generate recommendation
        core_count = tiers["core"]["node_count"]
        extended_count = tiers["extended"]["node_count"]

        if core_count >= 10:
            recommendation = "Start with 'core' tier - sufficient high-confidence results for focused analysis."
        elif core_count >= 5:
            recommendation = "Use 'core' tier for initial understanding, then expand to 'extended' if needed."
        else:
            recommendation = f"Core tier has only {core_count} nodes. Use 'extended' tier for better coverage."

        output = {
            "entry_token": start,
            "tiers": tiers,
            "recommendation": recommendation,
            "mode": "multi_tier",
        }

        # Enrich with TDA field metrics
        output = self.tda_enricher.enrich_multi_tier_results(output)

        return output

    def get_symbol(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Get symbol details.

        Args:
            symbol_name: Symbol name (without "sym::" prefix)

        Returns:
            Dict with symbol details or None if not found
        """
        node_id = f"sym::{symbol_name}"
        node = self.registry_adapter.get_node(node_id)

        if not node:
            return None

        # Get edges
        edges = self.registry_adapter.get_edges_from(node_id)

        return {
            "id": node.id,
            "type": node.type,
            "tags": list(node.tags),
            "metadata": node.metadata,
            "edges": [
                {
                    "dst": e.dst,
                    "weight": e.weight,
                    "kind": e.kind,
                }
                for e in edges
            ],
        }

    def get_category(self, category_name: str) -> Optional[Dict[str, Any]]:
        """Get category details.

        Args:
            category_name: Category name (without "cat::" prefix)

        Returns:
            Dict with category details or None if not found
        """
        node_id = f"cat::{category_name}"
        node = self.registry_adapter.get_node(node_id)

        if not node:
            return None

        # Get all symbols in this category (reverse edges)
        all_edges = self.registry_adapter.get_all_edges()
        symbols_in_category = [
            e.src for e in all_edges
            if e.dst == node_id and e.kind == "category"
        ]

        return {
            "id": node.id,
            "type": node.type,
            "tags": list(node.tags),
            "metadata": node.metadata,
            "symbol_count": len(symbols_in_category),
            "symbols": symbols_in_category[:10],  # First 10
        }

    def list_categories(self) -> List[str]:
        """List all categories.

        Returns:
            List of category IDs
        """
        all_nodes = self.registry_adapter.get_all_nodes()
        categories = [n.id for n in all_nodes if n.type == "category"]
        return sorted(categories)

    def list_symbols(self, limit: int = 100) -> List[str]:
        """List all symbols.

        Args:
            limit: Maximum number of symbols to return

        Returns:
            List of symbol IDs
        """
        all_nodes = self.registry_adapter.get_all_nodes()
        symbols = [n.id for n in all_nodes if n.type == "symbol"]
        return sorted(symbols)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.

        Returns:
            Dict with statistics from loaded index (if available) or scan results
        """
        # If registry is loaded from database, return stats from it
        if isinstance(self.registry_adapter, SQLiteRegistryAdapter):
            all_nodes = self.registry_adapter.get_all_nodes()
            all_edges = self.registry_adapter.get_all_edges()

            # Count by type
            symbols = [n for n in all_nodes if n.type == "symbol"]
            categories = [n for n in all_nodes if n.type == "category"]

            return {
                "workspace_root": str(self.workspace_root),
                "source": "loaded_index",
                "graph": {
                    "total_nodes": len(all_nodes),
                    "total_edges": len(all_edges),
                    "symbols": len(symbols),
                    "categories": len(categories),
                },
            }

        # Otherwise, require scan_workspace to have been called
        if not self.scan_stats or not self.build_stats:
            return {
                "error": "No index loaded. Either mount a workspace with existing registry.db or call scan_workspace() first.",
                "workspace_root": str(self.workspace_root),
            }

        return {
            "workspace_root": str(self.workspace_root),
            "source": "fresh_scan",
            "scan": {
                "files_scanned": self.scan_stats.files_scanned,
                "symbols_kept": self.scan_stats.symbols_kept,
            },
            "index": {
                "nodes_created": self.build_stats.nodes_created,
                "edges_created": self.build_stats.edges_created,
                "categories_created": self.build_stats.categories_created,
            },
            "graph": {
                "total_nodes": len(self.registry_adapter.get_all_nodes()),
                "total_edges": len(self.registry_adapter.get_all_edges()),
            },
        }

    def clear(self):
        """Clear all data (for testing)."""
        self.scan_adapter.clear()
        self.registry_adapter.clear()
        self.scan_stats = None
        self.build_stats = None

    # Phase 3.5: Upstream Navigation Methods

    def tda_find_upstream(
        self,
        symbol: str,
        top_k: int = 5,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """Find upstream sources for a symbol.

        Args:
            symbol: Symbol ID
            top_k: Number of top sources to return
            max_depth: Maximum traversal depth (hard limit: 2)

        Returns:
            Dict with upstream sources
        """
        if not self.upstream_navigator:
            return {
                "error": "UpstreamNavigator not initialized. Run TDA Phase 2.5 first."
            }

        try:
            sources = self.upstream_navigator.find_upstream_sources(
                node=symbol,
                top_k=top_k,
                max_depth=max_depth
            )

            return {
                "symbol": symbol,
                "sources": [
                    {
                        "symbol": src.symbol,
                        "tension": src.tension,
                        "distance": src.distance,
                        "source_type": src.source_type,
                        "forward_magnitude": src.forward_magnitude,
                        "score": src.score
                    }
                    for src in sources
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    def tda_escape_sink(self, symbol: str) -> Dict[str, Any]:
        """Escape from a sink node using upstream navigation.

        Args:
            symbol: Sink node ID

        Returns:
            Dict with escape result
        """
        if not self.upstream_navigator:
            return {
                "error": "UpstreamNavigator not initialized. Run TDA Phase 2.5 first."
            }

        try:
            result = self.upstream_navigator.escape_sink(symbol)

            return {
                "symbol": symbol,
                "escape_to": result.escape_to,
                "confidence": result.confidence,
                "reason": result.reason,
                "upstream_sources": [
                    {
                        "symbol": src.symbol,
                        "tension": src.tension,
                        "distance": src.distance,
                        "source_type": src.source_type,
                        "forward_magnitude": src.forward_magnitude,
                        "score": src.score
                    }
                    for src in result.upstream_sources
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    def tda_get_field_vector(self, symbol: str) -> Dict[str, Any]:
        """Get field vector and energy state for a symbol from TDA manifold states.

        Args:
            symbol: Symbol ID (e.g., 'sym::CQEIndexPipeline')

        Returns:
            Dict with field vector, energy, and topology data
        """
        from core.cqe.tda_bridge import TDABridge

        tda_bridge = TDABridge(self.workspace_root)

        # Get CQE graph for degree information
        cqe_index_path = self.workspace_root / ".quro_context" / "cqe_index.db"
        if not cqe_index_path.exists():
            return {"error": "CQE index not found"}

        from adapters.graph.sqlite import SQLiteGraphAdapter

        with SQLiteGraphAdapter(cqe_index_path) as graph:
            out_degree = graph.out_degree(symbol)
            in_degree = graph.in_degree(symbol)

            # Get complete node state from TDA bridge
            node_state = tda_bridge.get_node_state(symbol, out_degree, in_degree)

            # Get energy breakdown from TDA bridge
            tda_bridge._load_manifold_states()
            state = tda_bridge._state_cache.get(symbol, {})
            energy_data = state.get("energy", {})

            return {
                "symbol": symbol,
                "vector": {
                    "magnitude": node_state.field_magnitude,
                },
                "energy": {
                    "potential": energy_data.get("potential", 0.0),
                    "kinetic": energy_data.get("kinetic", 0.0),
                    "total": node_state.energy_total,
                },
                "field_role": node_state.field_role.value,
                "topology": {
                    "gravity": node_state.gravity_score,
                    "out_degree": out_degree,
                    "in_degree": in_degree,
                },
            }

    def tda_classify_role(self, symbol: str) -> Dict[str, Any]:
        """Classify node role based on anisotropic field.

        Args:
            symbol: Symbol ID

        Returns:
            Dict with role classification
        """
        if not self.upstream_navigator:
            return {
                "error": "UpstreamNavigator not initialized. Run TDA Phase 2.5 first."
            }

        try:
            role = self.upstream_navigator.classify_node_role(symbol)
            field_data = self.upstream_navigator.get_field_data(symbol)

            if not field_data:
                return {"error": f"No field data found for {symbol}"}

            return {
                "symbol": symbol,
                "role": role,
                "forward_magnitude": field_data.get("forward_magnitude", 0.0),
                "backward_tension": field_data.get("backward_tension", 0.0),
                "source_diversity": field_data.get("source_diversity", 0.0),
                "in_degree": field_data.get("in_degree", 0),
                "out_degree": field_data.get("out_degree", 0)
            }
        except Exception as e:
            return {"error": str(e)}