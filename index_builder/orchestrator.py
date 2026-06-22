"""Index Builder v3 - Orchestrator

@module quro.index_builder.orchestrator
@intent Main index builder that wires together all components
@constraint Pure orchestration - delegates to core/adapters
"""

from typing import List, Optional, Callable
from collections import defaultdict
from scanner.types import SymbolInfo
from index_builder.types import (
    GraphNode,
    GraphEdge,
    IndexResult,
    BuildStats,
    SymbolEnricherProtocol,
    EdgeWeightConfig,
    EnrichedSymbol,
    FilteredRefs,
    RegisteredEnricher,
    EnricherSpec,
    SystemArchitectureError,
)
from index_builder.core.converter import SymbolConverter
from index_builder.adapters.protocol import RegistryAdapter


class IndexBuilder:
    """Main index builder orchestrator.

    Coordinates the complete index building pipeline:
    1. Enrich SymbolInfo through plugins
    2. Convert EnrichedSymbol to GraphNode
    3. Create category nodes
    4. Create edges (category, calls, imports)
    5. Save to registry adapter

    Pure orchestration - delegates to specialized components.
    """

    def __init__(
        self,
        adapter: RegistryAdapter,
        enrichers: Optional[List[SymbolEnricherProtocol]] = None,
        edge_config: Optional[EdgeWeightConfig] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize index builder.

        Args:
            adapter: Registry adapter for graph storage
            enrichers: Domain-specific semantic enrichers
            edge_config: Custom edge weight settings
            progress_callback: Optional callback for progress updates
        """
        self.adapter = adapter
        self.progress_callback = progress_callback
        self.enrichers = enrichers or []
        self.converter = SymbolConverter(edge_config)

        # Enricher registry with contract verification
        self._enricher_registry: List[RegisteredEnricher] = []

        # Statistics
        self._stats = {
            "symbols_processed": 0,
            "symbols_indexed": 0,
            "symbols_skipped": 0,
            "nodes_created": 0,
            "edges_created": 0,
            "categories_created": 0,
            "containment_edges": 0,
        }

    def _inject_containment_edges(self, symbols: List[SymbolInfo]) -> List[GraphEdge]:
        """Inject CONTAINS edges from Classes to their Methods.

        These are structural edges for discovery only, not execution.
        Weight is structure-normalized: base * (mass(M_i) / Σ mass(M_j))
        to prevent bias between classes with different method counts.

        Args:
            symbols: List of all symbols from scanner

        Returns:
            List of containment edges (Class → Method)
        """
        containment_edges = []

        # Group symbols by file
        by_file = defaultdict(list)
        for sym in symbols:
            by_file[sym.symbol.file_path].append(sym)

        # For each file, find Class → Method relationships
        for file_path, file_symbols in by_file.items():
            classes = [s for s in file_symbols if s.symbol.kind == 'class']
            methods = [s for s in file_symbols
                       if s.symbol.kind in ('method', 'async_method')]

            # Sort classes by line number to determine boundaries
            classes_sorted = sorted(classes, key=lambda s: s.symbol.line)

            for i, class_sym in enumerate(classes_sorted):
                class_id = f"sym::{class_sym.symbol.name}"

                # Determine the boundary for this class
                # Methods belong to this class if they're after this class
                # but before the next class (if any)
                class_start = class_sym.symbol.line
                class_end = classes_sorted[i + 1].symbol.line if i + 1 < len(classes_sorted) else float('inf')

                # Find methods defined in this class (between class_start and class_end)
                class_methods = []
                for method_sym in methods:
                    if class_start < method_sym.symbol.line < class_end:
                        class_methods.append(method_sym)

                # Calculate structure-normalized weights
                if class_methods:
                    # Calculate mass for each method (using line count as proxy)
                    method_masses = []
                    for method_sym in class_methods:
                        # Estimate method size: use a simple heuristic
                        # In absence of end_line, use uniform mass
                        mass = 1.0  # Uniform distribution for now
                        method_masses.append(mass)

                    total_mass = sum(method_masses)
                    base_weight = 0.1  # Base weight to ensure tau survival

                    # Create edges with normalized weights
                    for method_sym, mass in zip(class_methods, method_masses):
                        method_id = f"sym::{method_sym.symbol.name}"

                        # Structure-normalized weight: base * (mass_i / total_mass)
                        normalized_weight = base_weight * (mass / total_mass)

                        edge = GraphEdge(
                            src=class_id,
                            dst=method_id,
                            weight=normalized_weight,
                            kind="contains",
                            metadata={
                                "layer": "structural",
                                "purpose": "discovery",
                                "is_execution_edge": False,
                                "normalization": "structure_normalized",
                                "method_mass": mass,
                                "total_class_mass": total_mass,
                            }
                        )
                        containment_edges.append(edge)
                        self._stats["containment_edges"] += 1

        return containment_edges

    def register_enricher(
        self,
        enricher: SymbolEnricherProtocol,
        priority: int,
        spec: EnricherSpec,
    ) -> None:
        """Register an enricher with contract verification.

        Runs smoke tests at system startup to verify enricher contract.
        Raises SystemArchitectureError if contract is invalid.

        Args:
            enricher: Enricher implementation
            priority: Execution priority (lower = earlier)
            spec: Formal contract specification

        Raises:
            SystemArchitectureError: If enricher contract verification fails
        """
        # Verify enricher contract
        if not self._verify_spec(enricher, spec):
            raise SystemArchitectureError(
                f"Enricher '{spec.name}' contract verification failed. "
                "System refuses to start with invalid enricher."
            )

        # Register and sort by priority
        registered = RegisteredEnricher(enricher=enricher, priority=priority, spec=spec)
        self._enricher_registry.append(registered)
        self._enricher_registry.sort(key=lambda x: x.priority)

    def _verify_spec(
        self,
        enricher: SymbolEnricherProtocol,
        spec: EnricherSpec,
    ) -> bool:
        """Verify enricher satisfies its contract specification.

        Runs smoke tests to ensure:
        1. Enricher accepts inputs matching input_boundary
        2. Enricher produces outputs matching output_boundary
        3. Enricher doesn't violate invariants

        Args:
            enricher: Enricher to verify
            spec: Contract specification

        Returns:
            True if contract is valid, False otherwise
        """
        # Create a minimal test symbol
        from scanner.types import SymbolInfo, ParsedSymbol, SymbolFeatures

        test_symbol = SymbolInfo(
            symbol=ParsedSymbol(
                name="test_symbol",
                kind="function",
                file_path="test.py",
                line=1,
                char=0,
                calls=(),
                imports=(),
            ),
            features=SymbolFeatures(
                behavioral_tags=tuple(spec.input_boundary.required_tags),
                structural_tags=(),
                risk_anchors=(),
            ),
            fingerprint="test_fingerprint_0000",
        )

        test_enriched = EnrichedSymbol(
            base=test_symbol,
            semantic_tags=tuple(spec.input_boundary.required_tags),
            intent="test_intent",
        )

        # Verify input boundary accepts test symbol
        if not spec.input_boundary.validate(test_enriched):
            return False

        # Run enricher
        try:
            result = enricher.enrich(test_enriched)
        except Exception:
            # Enricher crashed on valid input
            return False

        # Verify output boundary
        if not spec.output_boundary.validate(result):
            return False

        return True

    def build_index(self, symbols: List[SymbolInfo]) -> BuildStats:
        """Build index from list of symbols.

        Uses two-pass enrichment:
        - Pass 1: Build graph structure with non-topology enrichers
        - Pass 2: Run topology-aware enrichers (HubPressureEnricher)

        Args:
            symbols: List of SymbolInfo from scanner

        Returns:
            Build statistics
        """
        self._reset_stats()

        # Store symbols for same-file edge matching
        self._all_symbols = symbols

        # Identify topology-aware enrichers
        topology_enrichers = {"HubPressureEnricher"}

        # Pass 1: Build graph structure
        self._report_progress("Pass 1: Building graph structure...")
        for symbol_info in symbols:
            self._report_progress(f"Indexing {symbol_info.symbol.name}")
            self.index_symbol(symbol_info, pass_num=1, topology_enrichers=topology_enrichers)

        # Inject containment edges after Pass 1
        self._report_progress("Injecting containment edges (Class → Method)...")
        containment_edges = self._inject_containment_edges(symbols)
        for edge in containment_edges:
            self.adapter.save_edge(edge)
            self._stats["edges_created"] += 1

        # Pass 2: Topology-aware enrichment
        if any(reg.spec.name in topology_enrichers for reg in self._enricher_registry):
            self._report_progress("Pass 2: Running topology-aware enrichers...")
            for symbol_info in symbols:
                self._update_symbol_tags(symbol_info, pass_num=2, topology_enrichers=topology_enrichers)

        return self._get_stats()

    def index_symbol(
        self,
        symbol_info: SymbolInfo,
        pass_num: int = 1,
        topology_enrichers: set = None,
    ) -> IndexResult:
        """Index a single symbol.

        Args:
            symbol_info: Symbol information from scanner
            pass_num: Pass number (1 or 2)
            topology_enrichers: Set of topology-aware enricher names

        Returns:
            IndexResult with nodes and edges created
        """
        if topology_enrichers is None:
            topology_enrichers = set()

        self._stats["symbols_processed"] += 1

        # Base wrap
        filtered_refs = FilteredRefs(
            calls=tuple(symbol_info.symbol.calls),
            imports=tuple(symbol_info.symbol.imports),
            inherits=tuple(getattr(symbol_info.symbol, "inherits", ())),
            attributes=tuple(getattr(symbol_info.symbol, "attr_accesses", ()))
        )
        enriched = EnrichedSymbol(
            base=symbol_info,
            semantic_tags=tuple(symbol_info.features.behavioral_tags + symbol_info.features.structural_tags + symbol_info.features.risk_anchors),
            filtered_refs=filtered_refs
        )

        # Phase 2: Run through Semantic Enrichment Pipeline
        # Use registered enrichers if available, otherwise fall back to legacy list
        enrichers_to_run = (
            [reg.enricher for reg in self._enricher_registry]
            if self._enricher_registry
            else self.enrichers
        )

        # Filter enrichers based on pass number
        for i, enricher_item in enumerate(enrichers_to_run):
            # Get enricher name from registry if available
            enricher_name = None
            if self._enricher_registry and i < len(self._enricher_registry):
                enricher_name = self._enricher_registry[i].spec.name

            # Skip topology enrichers in pass 1
            if pass_num == 1 and enricher_name in topology_enrichers:
                continue

            # Only run topology enrichers in pass 2
            if pass_num == 2 and enricher_name not in topology_enrichers:
                continue

            enriched = enricher_item.enrich(enriched)

        # Only create nodes/edges in pass 1
        if pass_num == 1:
            # Convert to graph node
            symbol_node = self.converter.to_graph_node(enriched)

            # Create category nodes
            category_nodes = self.converter.create_category_nodes(enriched)

            # Build enriched symbols list for same-file matching
            # Convert all SymbolInfo to EnrichedSymbol for edge resolution
            all_enriched = []
            if hasattr(self, '_all_symbols'):
                for sym_info in self._all_symbols:
                    filtered_refs = FilteredRefs(
                        calls=tuple(sym_info.symbol.calls),
                        imports=tuple(sym_info.symbol.imports),
                        inherits=tuple(getattr(sym_info.symbol, "inherits", ())),
                        attributes=tuple(getattr(sym_info.symbol, "attr_accesses", ()))
                    )
                    enriched_sym = EnrichedSymbol(
                        base=sym_info,
                        semantic_tags=tuple(sym_info.features.behavioral_tags + sym_info.features.structural_tags),
                        filtered_refs=filtered_refs
                    )
                    all_enriched.append(enriched_sym)

            # Create edges with same-file priority matching
            category_edges = self.converter.create_category_edges(
                symbol_node, category_nodes
            )
            call_edges = self.converter.create_call_edges(enriched, symbol_node, all_enriched)
            import_edges = self.converter.create_import_edges(enriched, symbol_node)
            inherit_edges = self.converter.create_inheritance_edges(enriched, symbol_node)
            attr_access_edges = self.converter.create_attr_access_edges(enriched, symbol_node)

            all_edges = category_edges + call_edges + import_edges + inherit_edges + attr_access_edges

            # Inject containment edges (Class → Method) for discovery
            if pass_num == 1 and not hasattr(self, '_containment_edges_injected'):
                # Mark that we'll inject containment edges after all symbols are processed
                self._containment_edges_injected = False

            # Save to adapter
            self.adapter.save_node(symbol_node)
            self._stats["nodes_created"] += 1

            # Save category nodes (deduplicate)
            unique_categories = {}
            for cat_node in category_nodes:
                if cat_node.id not in unique_categories:
                    unique_categories[cat_node.id] = cat_node

            for cat_node in unique_categories.values():
                if not self.adapter.node_exists(cat_node.id):
                    self.adapter.save_node(cat_node)
                    self._stats["categories_created"] += 1

            # Save edges
            for edge in all_edges:
                self.adapter.save_edge(edge)
                self._stats["edges_created"] += 1

            self._stats["symbols_indexed"] += 1

            return IndexResult(
                symbol_node=symbol_node,
                category_nodes=tuple(unique_categories.values()),
                edges=tuple(all_edges),
            )
        else:
            # Pass 2: Return empty result (tags updated in place)
            return IndexResult(
                symbol_node=GraphNode(id="", type="", tags=()),
                skipped=True,
            )

    def _update_symbol_tags(
        self,
        symbol_info: SymbolInfo,
        pass_num: int = 2,
        topology_enrichers: set = None,
    ):
        """Update symbol tags with topology-aware enrichers.

        Args:
            symbol_info: Symbol information
            pass_num: Pass number (should be 2)
            topology_enrichers: Set of topology-aware enricher names
        """
        if topology_enrichers is None:
            topology_enrichers = set()

        # Reconstruct enriched symbol
        filtered_refs = FilteredRefs(
            calls=tuple(symbol_info.symbol.calls),
            imports=tuple(symbol_info.symbol.imports),
            inherits=tuple(getattr(symbol_info.symbol, "inherits", ())),
            attributes=tuple(getattr(symbol_info.symbol, "attr_accesses", ()))
        )

        # Get existing node to preserve tags from pass 1
        symbol_id = f"sym::{symbol_info.symbol.name}"
        existing_node = self.adapter.get_node(symbol_id)

        if not existing_node:
            return  # Node doesn't exist, skip

        enriched = EnrichedSymbol(
            base=symbol_info,
            semantic_tags=existing_node.tags,  # Start with existing tags
            filtered_refs=filtered_refs
        )

        # Run topology enrichers
        for reg in self._enricher_registry:
            if reg.spec.name in topology_enrichers:
                enriched = reg.enricher.enrich(enriched)

        # Update node tags in registry
        updated_node = GraphNode(
            id=existing_node.id,
            type=existing_node.type,
            tags=enriched.semantic_tags,
            metadata=existing_node.metadata,
        )
        self.adapter.save_node(updated_node)

    def _report_progress(self, message: str):
        """Report progress via callback.

        Args:
            message: Progress message
        """
        if self.progress_callback:
            self.progress_callback(message)

    def _reset_stats(self):
        """Reset statistics."""
        for key in self._stats:
            self._stats[key] = 0

    def _get_stats(self) -> BuildStats:
        """Get current statistics.

        Returns:
            BuildStats object
        """
        return BuildStats(**self._stats)
