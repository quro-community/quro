"""
Pass 4: Semantic Center Detection (Design 99)

@module quro.tda.phase3_5.pass4_center_detection
@intent Partition the codebase graph into semantic centers using a dual-role approach:
        Community = spatial partition (role type + energy band)
        Attractor = semantic center within each community (sink convergence points)

Architecture:
  Community = 地图区域 (role type + energy band partition)
  Attractor = 城市中心 (sink nodes where code flow converges)

Phase 3.7: Structural Coupling Graph (SCG)
  Detects how dependency flow geometry forces symbols to coexist.
  Three coupling sources:
    1. Shared upstream pressure: A ← X → B
    2. Shared downstream sink:  A → Z ← B
    3. Traversal convergence:   repeated appearance of X in paths

Algorithm:
  1. Load graph adjacency using GraphAdapter (uses adjacency_cache.pkl by default)
  2. Partition by (role_type, energy_band) → communities
  3. Prune small communities (merge into nearest)
  4. Per community: identify attractors (field_role=attractor, sink+sink, high-energy sink)
  5. Entry points: attractors first, then non-generic high-centrality symbols
  6. Build structural coupling graph (Phase 3.7)
  7. Detect structural clusters via Louvain community detection
  8. Compute inter-center coupling relationships

Performance Note:
  This phase uses GraphAdapter which prioritizes adjacency_cache.pkl (fast)
  over graph_events.jsonl (slow 20GB fallback). Run Phase 2 to generate the cache.
"""

import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from ..interfaces.graph import GraphInterface
from ..adapters import GraphAdapter
from ..phase2.schema import SymbolManifoldState
from . import (
    TopologicalArchetype,
    SemanticCenter,
    SemanticCenterSCG,
    EntryPointInfo,
    StructureProfile,
    CenterTopology,
    NavigationHint,
    StructuralArchetype,
    StructuralCluster,
    CoupledCenters,
    StructuralCouplingReport,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Minimum community size (centers smaller than this are merged into nearest)
MIN_COMMUNITY_SIZE = 50

# Target number of communities (will aim for this many if possible)
TARGET_COMMUNITIES = 8

# Maximum iterations for label propagation
MAX_PROPAGATION_ITERS = 10

# Generic symbols to exclude from entry points (framework bootstrap, not business logic)
GENERIC_SYMBOLS = frozenset({
    "main", "__init__", "run", "start", "stop", "scan", "setup",
    "append", "insert", "get", "set", "add", "remove", "delete",
    "create", "update", "fetch", "read", "close", "open", "write",
    "validate", "execute", "handle", "process", "dispatch",
    "__call__", "__enter__", "__exit__", "__str__", "__repr__",
    "__len__", "__getitem__", "__setitem__", "__delitem__",
    "__contains__", "__iter__", "__next__", "__eq__", "__hash__",
    "on_startup", "on_shutdown", "cleanup", "teardown",
})

# Generic prefixes (symbols starting with these are excluded)
GENERIC_PREFIXES = ("cat::", "_", "__")

# Generic suffixes (symbols ending with these are excluded)
GENERIC_SUFFIXES = ("_cb", "_fn", "_handler", "_callback", "_cb_", "_cb")

# =============================================================================
# Phase 3.7: Structural Coupling Graph (SCG)
# =============================================================================

# BFS depth for coupling detection (max path length for shared-flow detection)
COUPLING_MAX_HOPS = 3

# Minimum cluster size (clusters smaller than this are filtered)
MIN_SC_CLUSTER_SIZE = 3

# Density threshold for "tight_coupling" archetype
TIGHT_COUPLING_DENSITY = 0.3

# Minimum shared sinks for "flow_convergent" archetype
MIN_SHARED_SINKS = 2

# Minimum coupling score for inter-center coupling to be reported
MIN_COUPLING_SCORE = 0.05


@dataclass
class CommunitySeed:
    """A seed node that defines a community."""
    symbol_id: str
    community_id: int
    role_type: str
    energy: float
    centrality: float


@dataclass
class CommunityInfo:
    """Information about a detected community."""
    seed_symbol: str
    symbol_ids: Set[str] = field(default_factory=set)
    role_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total_centrality: float = 0.0
    total_energy: float = 0.0
    total_friction: float = 0.0
    total_clustering: float = 0.0
    max_energy: float = 0.0
    # Attractors: symbols that are the semantic centers of this community
    # (where code flow converges within this community)
    attractors: List[str] = field(default_factory=list)


class CenterDetector:
    """Detect semantic centers using community detection + label propagation."""

    def __init__(self, workspace_root: Optional[Path] = None):
        """Initialize center detector.

        Args:
            workspace_root: Workspace root for loading Phase-1 events
        """
        self.workspace_root = workspace_root or Path.cwd()
        self._adjacency: Dict[str, List[str]] = defaultdict(list)
        self._in_neighbors: Dict[str, List[str]] = defaultdict(list)
        self._communities: Dict[str, int] = {}  # symbol → community_id

        # SCG data (populated during detect_centers)
        self._structural_clusters: List[StructuralCluster] = []
        self._coupled_centers: List[CoupledCenters] = []

    def detect_centers(
        self,
        manifold_states: List[SymbolManifoldState],
        field_data_path: Optional[Path] = None,
    ) -> List[SemanticCenterSCG]:
        """Detect semantic centers via community detection + label propagation.

        Algorithm:
          1. Load graph adjacency using GraphAdapter (uses adjacency_cache.pkl by default)
          2. Seed communities from diverse hub roles + energy clusters
          3. Propagate labels via label propagation (weighted by energy similarity)
          4. Prune small communities (merge into nearest)
          5. Derive centers with archetypes and entry points
          6. Build Structural Coupling Graph (Phase 3.7)
          7. Enrich centers with structural coupling data

        Args:
            manifold_states: All symbol manifold states
            field_data_path: Optional path to .quro_context/tda/ for loading adjacency

        Returns:
            List of SemanticCenterSCG (enriched with structural coupling)
        """
        field_data_path = field_data_path or self.workspace_root / ".quro_context" / "tda"

        # Step 1: Build symbol registry
        symbol_map = {sms.symbol: sms for sms in manifold_states}
        logger.info("Detecting centers from %d manifold states", len(symbol_map))

        # Step 2: Load graph adjacency from Phase-1 events
        self._load_adjacency(field_data_path)

        # Step 3: Seed communities from diverse hub roles
        seeds = self._seed_communities(symbol_map)
        logger.info("Seeded %d initial communities", len(seeds))

        if not seeds:
            logger.warning("No seed communities found, falling back to centrality-based seeding")
            seeds = self._fallback_seeding(symbol_map)
            logger.info("Created %d fallback communities based on centrality", len(seeds))

        # Step 4: Propagate labels via label propagation
        communities = self._community_detection(symbol_map, seeds)
        logger.info("Community detection: %d symbols assigned to %d communities",
                    len(self._communities), len(communities))

        # Step 5: Prune small communities (merge into nearest)
        communities = self._prune_small_communities(communities, symbol_map)
        logger.info("After pruning: %d centers remain", len(communities))

        # Step 6: Derive SemanticCenter from communities
        centers = self._derive_centers(communities, symbol_map)

        # Sort by size descending
        centers.sort(key=lambda c: c.size, reverse=True)

        # Re-index centers by order (C0, C1, ...)
        for i, center in enumerate(centers):
            center.id = f"C{i}"

        logger.info("Detected %d semantic centers", len(centers))

        # Phase 3.7: Structural Coupling Graph (SCG)
        logger.info("Building Structural Coupling Graph...")
        coupling_graph = build_coupling_graph(self._adjacency, symbol_map)
        logger.info("Coupling graph: %d nodes, %d edges",
                   coupling_graph.number_of_nodes(),
                   coupling_graph.number_of_edges())

        structural_clusters, symbol_to_cluster = detect_structural_clusters(
            coupling_graph, symbol_map, self._adjacency
        )
        logger.info("Detected %d structural clusters", len(structural_clusters))

        coupled_centers = compute_inter_center_coupling(
            centers, structural_clusters, coupling_graph, symbol_map, symbol_to_cluster, self._communities
        )
        logger.info("Found %d coupled center pairs", len(coupled_centers))

        enriched_centers = enrich_centers_with_scg(
            centers, structural_clusters, coupled_centers, coupling_graph, symbol_map, symbol_to_cluster, self._communities
        )
        logger.info("Enriched %d centers with SCG data", len(enriched_centers))

        # Store SCG data for retrieval
        self._structural_clusters = structural_clusters
        self._coupled_centers = coupled_centers

        return enriched_centers

    def _load_adjacency(self, field_data_path: Path) -> None:
        """Load graph adjacency using GraphAdapter.

        GraphAdapter automatically selects the best available source:
        1. adjacency_cache.pkl (Phase 2 output) - FASTEST
        2. field_data_cache.pkl (Phase 4 output)
        3. graph_events.jsonl (20GB, slow fallback)

        This method is called by detect_centers() to populate:
        - self._adjacency: forward neighbors (src -> [dsts])
        - self._in_neighbors: reverse neighbors (dst -> [srcs])
        """
        import time

        start_time = time.time()
        logger.info("Loading graph adjacency using GraphAdapter...")

        # Log available sources
        available = GraphAdapter.list_available_sources(field_data_path)
        if available:
            logger.info("Available graph sources: %s", ", ".join(available))
        else:
            logger.warning("No graph sources found in %s", field_data_path)

        # Create graph using adapter (auto-selects best source)
        graph = GraphAdapter.create(field_data_path)

        # Log which source is being used
        if hasattr(graph, 'metadata') and graph.metadata:
            meta = graph.metadata
            logger.info(
                "Using graph source: %s (created by %s at %s)",
                meta.source, meta.phase, meta.created_at
            )
            logger.info(
                "Graph stats: %d nodes, %d edges",
                meta.num_nodes, meta.num_edges
            )

        # Populate adjacency dicts from graph interface
        for node in graph.get_all_nodes():
            self._adjacency[node] = graph.get_out_neighbors(node)
            self._in_neighbors[node] = graph.get_in_neighbors(node)

        elapsed = time.time() - start_time
        logger.info(
            "Loaded adjacency in %.2fs: %d nodes, %d edges",
            elapsed, len(self._adjacency), sum(len(v) for v in self._adjacency.values())
        )

    def _seed_communities(
        self,
        symbol_map: Dict[str, SymbolManifoldState],
    ) -> List[CommunitySeed]:
        """Seed communities from top non-generic symbols by centrality + energy diversity.

        Strategy: Pick the top N non-generic, non-category symbols by centrality.
        Ensure diversity by also including symbols from different energy bands.
        This ensures we start with meaningful business-logic symbols.
        """
        seeds = []
        community_id = 0

        # Collect all non-generic, non-category symbols
        candidates = []
        for sym_id, sms in symbol_map.items():
            if not sms.topology:
                continue
            if self._is_generic_symbol(sym_id):
                continue
            centrality = sms.topology.centrality
            energy = 0.0
            if sms.energy:
                energy = sms.energy.get("total", 0.0)
            candidates.append((sym_id, centrality, energy, sms.role.type))

        if not candidates:
            return []

        # Sort by centrality descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Take top N by centrality
        target = TARGET_COMMUNITIES
        top_candidates = candidates[:target * 3]  # Take more, then filter for diversity

        # Pick seeds ensuring energy diversity (different bands)
        # Energy range: 2.5 to 6.1 based on data analysis
        energy_bands = 4  # Split into 4 bands
        band_size = (6.1 - 2.5) / energy_bands
        picked_in_band = [0] * energy_bands
        max_per_band = 3

        for sym_id, centrality, energy, role_type in top_candidates:
            if community_id >= target:
                break

            band = min(int((energy - 2.5) / band_size), energy_bands - 1) if band_size > 0 else 0
            if picked_in_band[band] >= max_per_band:
                continue

            seeds.append(CommunitySeed(
                symbol_id=sym_id,
                community_id=community_id,
                role_type=role_type,
                energy=energy,
                centrality=centrality,
            ))
            picked_in_band[band] += 1
            community_id += 1

        # If still not enough seeds, add more from remaining candidates
        if len(seeds) < 3:
            for sym_id, centrality, energy, role_type in top_candidates:
                if any(s.symbol_id == sym_id for s in seeds):
                    continue
                seeds.append(CommunitySeed(
                    symbol_id=sym_id,
                    community_id=community_id,
                    role_type=role_type,
                    energy=energy,
                    centrality=centrality,
                ))
                community_id += 1
                if community_id >= target:
                    break

        return seeds

    def _is_generic_symbol(self, symbol: str) -> bool:
        """Check if symbol is a generic framework bootstrap symbol.

        These are framework-level symbols, not business logic.
        Exclude them from entry points and community seeds.
        """
        if symbol.startswith(GENERIC_PREFIXES):
            return True
        name = symbol.replace("sym::", "")
        # Check exact generic name match
        if name in GENERIC_SYMBOLS:
            return True
        # Check generic suffixes
        for suffix in GENERIC_SUFFIXES:
            if name.endswith(suffix):
                return True
        return False

    def _community_detection(
        self,
        symbol_map: Dict[str, SymbolManifoldState],
        seeds: List[CommunitySeed],
    ) -> Dict[int, CommunityInfo]:
        """Partition symbols into communities using role type + energy band clustering.

        Strategy: Use the natural role distribution and energy levels to create
        semantically meaningful partitions. This avoids the hub-dominance problem
        in connectivity-based clustering.

        Algorithm:
          1. For each symbol, compute its role type + energy band
          2. Group symbols into communities based on (role, energy_band) tuple
          3. Result: each community has a distinct topological character
        """
        import time
        start_time = time.time()

        communities: Dict[int, CommunityInfo] = {}
        self._communities = {}

        # Energy range from data analysis
        ENERGY_MIN = 2.5
        ENERGY_MAX = 6.1
        ENERGY_BANDS = 4  # Low / Medium / High / Very High

        band_size = (ENERGY_MAX - ENERGY_MIN) / ENERGY_BANDS

        # Community ID mapping: (role_type, energy_band) → community_id
        role_energy_map: Dict[tuple, int] = {}
        next_cid = 0

        for sym_id, sms in symbol_map.items():
            role = sms.role.type if sms else "leaf"
            energy = 0.0
            if sms and sms.energy:
                energy = sms.energy.get("total", 0.0)

            # Compute energy band
            if energy <= ENERGY_MIN:
                band = 0
            elif energy >= ENERGY_MAX:
                band = ENERGY_BANDS - 1
            else:
                band = min(int((energy - ENERGY_MIN) / band_size), ENERGY_BANDS - 1)

            key = (role, band)

            if key not in role_energy_map:
                role_energy_map[key] = next_cid
                communities[next_cid] = CommunityInfo(seed_symbol=sym_id)
                next_cid += 1

            cid = role_energy_map[key]
            self._communities[sym_id] = f"C{cid}"  # Store as string "C{id}"
            communities[cid].symbol_ids.add(sym_id)
            self._update_community_stats(communities[cid], sms)

        elapsed = time.time() - start_time
        logger.info(
            "Role-energy community detection: %d symbols in %d communities, %.1fs",
            len(self._communities), len(communities), elapsed
        )

        return communities

    def _update_community_stats(
        self,
        community: CommunityInfo,
        sms: Optional[SymbolManifoldState],
    ) -> None:
        """Update community statistics with a new symbol."""
        if sms is None:
            return
        community.role_counts[sms.role.type] += 1
        if sms.topology:
            community.total_centrality += sms.topology.centrality
            community.total_clustering += sms.topology.clustering_coeff
        if sms.energy:
            community.total_energy += sms.energy.get("total", 0.0)
            community.max_energy = max(community.max_energy, sms.energy.get("total", 0.0))
        if hasattr(sms, "friction") and sms.friction is not None:
            community.total_friction += sms.friction

    def _prune_small_communities(
        self,
        communities: Dict[int, CommunityInfo],
        symbol_map: Dict[str, SymbolManifoldState],
    ) -> Dict[int, CommunityInfo]:
        """Merge communities smaller than MIN_COMMUNITY_SIZE into nearest community."""
        small_communities = [cid for cid, c in communities.items() if len(c.symbol_ids) < MIN_COMMUNITY_SIZE]

        if not small_communities:
            return communities

        logger.info("Pruning %d small communities (< %d symbols)", len(small_communities), MIN_COMMUNITY_SIZE)

        # For each small community, reassign symbols to largest remaining community
        for small_id in small_communities:
            small_symbols = communities[small_id].symbol_ids.copy()
            del communities[small_id]

            # Remove from community map
            for sym in small_symbols:
                del self._communities[sym]

            # Find largest remaining community
            if not communities:
                # Create a new fallback community
                fallback_id = max(communities.keys(), default=-1) + 1
                communities[fallback_id] = CommunityInfo(seed_symbol=f"fallback_{fallback_id}")
                for sym in small_symbols:
                    self._communities[sym] = f"C{fallback_id}"
                    communities[fallback_id].symbol_ids.add(sym)
                    self._update_community_stats(communities[fallback_id], symbol_map.get(sym))
            else:
                largest_id = max(communities.keys(), key=lambda cid: len(communities[cid].symbol_ids))
                for sym in small_symbols:
                    self._communities[sym] = f"C{largest_id}"
                    communities[largest_id].symbol_ids.add(sym)
                    self._update_community_stats(communities[largest_id], symbol_map.get(sym))

        # Re-index community IDs sequentially
        new_communities = {}
        new_id = 0
        id_map = {}
        for old_id in sorted(communities.keys()):
            id_map[old_id] = new_id
            new_communities[new_id] = communities[old_id]
            new_id += 1

        # Update community map with new IDs
        for sym in self._communities:
            old_cid = self._communities[sym]
            # Find the old_id that maps to the current community
            old_id = None
            for oid, nid in id_map.items():
                if f"C{oid}" == old_cid:
                    old_id = oid
                    break
            if old_id is not None and old_id in id_map:
                self._communities[sym] = f"C{id_map[old_id]}"

        return new_communities

    def _derive_centers(
        self,
        communities: Dict[int, CommunityInfo],
        symbol_map: Dict[str, SymbolManifoldState],
    ) -> List[SemanticCenter]:
        """Derive SemanticCenter from communities.

        Each SemanticCenter = one community.
        Entry points are derived from attractors first (convergence points),
        then by centrality for non-attractor communities.
        """
        centers = []
        total_communities = len(communities)

        for community_id, community in communities.items():
            if community_id % 5 == 0 or community_id == total_communities - 1:
                logger.info("Deriving centers: %d/%d communities processed",
                          community_id + 1, total_communities)

            if not community.symbol_ids:
                continue

            n = len(community.symbol_ids)

            # Identify attractors within this community
            # Attractors = where code flow converges (high in-degree, sinks, field_role=attractor)
            attractors = self._identify_attractors(community.symbol_ids, symbol_map)
            community.attractors = attractors
            logger.debug(
                "Center C%d: found %d attractors in %d symbols",
                community_id, len(attractors), n
            )

            # Compute archetype from role distribution
            archetype, confidence = self._derive_archetype(community.role_counts, n)

            # Compute density
            avg_centrality = community.total_centrality / n if n > 0 else 0.0
            density = avg_centrality  # Normalized by centrality as proxy

            # Compute structure profile
            total_fan_in = sum(
                len(self._in_neighbors.get(sym, [])) for sym in community.symbol_ids
            )
            total_fan_out = sum(
                len(self._adjacency.get(sym, [])) for sym in community.symbol_ids
            )
            avg_clustering = community.total_clustering / n if n > 0 else 0.0

            # Depth: max BFS depth from entry points
            depth = self._compute_depth(community.symbol_ids, symbol_map)

            # Structural profile
            structure_profile = self._build_structure_profile(
                total_fan_in / n if n > 0 else 0,
                total_fan_out / n if n > 0 else 0,
                depth,
                avg_clustering,
            )

            # Entry points: top centrality non-generic symbols within community
            entry_points = self._select_entry_points(community.symbol_ids, symbol_map)

            # Navigation hint
            navigation = self._build_navigation_hint(archetype, structure_profile, n)

            # Compute stable identity and members hash
            from . import compute_stable_id, compute_members_hash

            stable_id = compute_stable_id(entry_points, archetype.value, n)
            members_hash = compute_members_hash(community.symbol_ids)

            # Connected centers (filled in by inter-center graph pass)
            center = SemanticCenter(
                id=f"center_{community_id}",  # Will be re-indexed to C0, C1, ...
                size=n,
                density=round(density, 3),
                structure=structure_profile,
                topology=CenterTopology(
                    pattern=archetype.value,
                    pattern_confidence=round(confidence, 3),
                    entry_points=entry_points,
                    connected_centers=[],
                    connections=[],
                ),
                navigation=navigation,
                stable_id=stable_id,
                members_hash=members_hash,
            )
            centers.append(center)

        return centers

    def _derive_archetype(
        self,
        role_counts: Dict[str, int],
        total: int,
    ) -> tuple[TopologicalArchetype, float]:
        """Derive topological archetype from role distribution."""
        if total == 0:
            return TopologicalArchetype.TRANSITIONAL, 0.0

        hub_ratio = role_counts.get("hub", 0) / total
        sink_ratio = role_counts.get("sink", 0) / total
        leaf_ratio = role_counts.get("leaf", 0) / total
        bridge_ratio = role_counts.get("bridge", 0) / total

        # Archetype decision tree
        if hub_ratio > 0.4:
            return TopologicalArchetype.HUB, min(1.0, hub_ratio + 0.2)
        elif sink_ratio > 0.4:
            return TopologicalArchetype.SINK, min(1.0, sink_ratio + 0.2)
        elif hub_ratio > 0.2 and sink_ratio > 0.2:
            # Mixed hub + sink = transitional
            return TopologicalArchetype.TRANSITIONAL, 0.6
        elif bridge_ratio > 0.3:
            return TopologicalArchetype.CHAIN, min(1.0, bridge_ratio + 0.3)
        elif leaf_ratio > 0.5:
            return TopologicalArchetype.FANOUT, min(1.0, leaf_ratio + 0.2)
        else:
            return TopologicalArchetype.TRANSITIONAL, 0.5

    def _compute_depth(
        self,
        symbol_ids: Set[str],
        symbol_map: Dict[str, SymbolManifoldState],
    ) -> int:
        """Compute maximum depth from entry points within a center."""
        # Entry points = symbols with no incoming edges from within the center
        entry_points = []
        for sym in symbol_ids:
            in_neighbors = self._in_neighbors.get(sym, [])
            external_in = [n for n in in_neighbors if n not in symbol_ids]
            if not external_in:
                entry_points.append(sym)

        if not entry_points:
            entry_points = list(symbol_ids)[:1]  # Fallback: pick any

        # BFS from entry points to compute max depth
        max_depth = 0
        visited: Set[str] = set()
        queue = deque([(sym, 0) for sym in entry_points])
        processed = 0

        while queue:
            current, depth = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            max_depth = max(max_depth, depth)
            processed += 1

            # Progress logging for large basins
            if processed % 500 == 0:
                logger.debug("Depth computation: processed %d nodes, max_depth=%d",
                           processed, max_depth)

            # Follow outgoing edges within center
            for neighbor in self._adjacency.get(current, []):
                if neighbor in symbol_ids and neighbor not in visited:
                    queue.append((neighbor, depth + 1))

        return max_depth

    def _build_structure_profile(
        self,
        avg_fan_in: float,
        avg_fan_out: float,
        depth: int,
        avg_clustering: float,
    ) -> "StructureProfile":
        """Build structural profile for a center."""
        from . import StructureProfile

        # Classify fan-in/out levels
        if avg_fan_in > 5:
            fan_in_level = "high"
        elif avg_fan_in > 2:
            fan_in_level = "medium"
        else:
            fan_in_level = "low"

        if avg_fan_out > 5:
            fan_out_level = "high"
        elif avg_fan_out > 2:
            fan_out_level = "medium"
        else:
            fan_out_level = "low"

        # Cohesion from clustering
        if avg_clustering > 0.5:
            cohesion = "high"
        elif avg_clustering > 0.2:
            cohesion = "medium"
        else:
            cohesion = "low"

        return StructureProfile(
            fan_in=fan_in_level,
            fan_out=fan_out_level,
            depth=depth,
            cohesion=cohesion,
        )

    def _select_entry_points(
        self,
        symbol_ids: Set[str],
        symbol_map: Dict[str, SymbolManifoldState],
    ) -> List[EntryPointInfo]:
        """Select top entry points for a center.

        Priority:
        1. Attractors first (where code flow converges within community)
        2. Non-generic high-centrality symbols

        Attractors are the "city centers" of each community — they represent
        the real semantic purpose of that region.
        """
        from . import EntryPointInfo

        # Filter: exclude generic symbols
        non_generic = [s for s in symbol_ids if not self._is_generic_symbol(s)]

        if not non_generic:
            non_generic = list(symbol_ids)

        # Step 1: Identify attractors within this community
        attractors = self._identify_attractors(symbol_ids, symbol_map)

        # Step 2: Build entry points list — attractors first, then non-attractor high-centrality
        entry_points: List[EntryPointInfo] = []

        # Add attractors (max 3)
        for sym in attractors[:3]:
            if sym in non_generic:
                sms = symbol_map.get(sym)
                if not sms or not sms.topology:
                    continue
                centrality = sms.topology.centrality
                energy = 0.0
                if sms.energy:
                    energy = sms.energy.get("total", 0.0)

                reasons = ["attractor"]
                if centrality > 0.7:
                    reasons.append("high centrality")
                if sms.role.type == "hub":
                    reasons.append("hub node")
                if energy > 4.0:
                    reasons.append("high energy")

                entry_points.append(EntryPointInfo(
                    symbol=sym,
                    reachability_score=round(centrality, 3),
                    reason=", ".join(reasons),
                ))

        # Step 3: Fill remaining slots with non-attractor, non-generic symbols by centrality
        if len(entry_points) < 5:
            attractor_set = set(attractors)
            remaining = [s for s in non_generic if s not in attractor_set]
            scored = []
            for sym in remaining:
                sms = symbol_map.get(sym)
                if not sms or not sms.topology:
                    continue
                centrality = sms.topology.centrality
                energy = 0.0
                if sms.energy:
                    energy = sms.energy.get("total", 0.0)
                score = centrality * (1.0 + min(energy, 5.0) * 0.1)
                scored.append((sym, score, centrality, energy))

            scored.sort(key=lambda x: x[1], reverse=True)
            for sym, score, centrality, energy in scored[:5 - len(entry_points)]:
                sms = symbol_map[sym]
                reasons = []
                if centrality > 0.7:
                    reasons.append("high centrality")
                if sms.role.type == "hub":
                    reasons.append("hub node")
                if sms.role.type == "sink":
                    reasons.append("sink node")
                if sms.role.type == "bridge":
                    reasons.append("bridge node")
                if energy > 4.0:
                    reasons.append("high energy")
                reason = ", ".join(reasons) if reasons else "top centrality"

                entry_points.append(EntryPointInfo(
                    symbol=sym,
                    reachability_score=round(centrality, 3),
                    reason=reason,
                ))

        return entry_points

    def _identify_attractors(
        self,
        symbol_ids: Set[str],
        symbol_map: Dict[str, SymbolManifoldState],
    ) -> List[str]:
        """Identify attractors within a community.

        Attractors = symbols where code flow converges.
        They are the "city centers" of each community.

        Detection criteria:
        1. field_role == "attractor" (from Phase 2.5)
        2. High in-degree relative to out-degree (sink behavior)
        3. Terminal role type (real I/O, persistence, completion points)
        4. Low clustering (not part of tight local cliques)

        Filter out generic symbols.
        """
        attractor_candidates = []

        for sym in symbol_ids:
            sms = symbol_map.get(sym)
            if not sms:
                continue

            # Skip generic symbols
            if self._is_generic_symbol(sym):
                continue

            # Criterion 1: field_role indicates attractor
            if getattr(sms, "field_role", None) == "attractor":
                attractor_candidates.append((sym, sms, 3.0))  # weight=3 (highest)
                continue

            # Criterion 2: high in-degree / low out-degree (sink behavior)
            in_deg = len(self._in_neighbors.get(sym, []))
            out_deg = len(self._adjacency.get(sym, []))

            if in_deg > 0 and out_deg <= 2:
                # Strong sink behavior
                score = in_deg / (out_deg + 1)
                if sms.role.type == "sink":
                    score += 1.0
                attractor_candidates.append((sym, sms, score))

            # Criterion 3: terminal symbols with persistence semantics
            if sms.role.type == "sink" and in_deg >= 2:
                energy = 0.0
                if sms.energy:
                    energy = sms.energy.get("total", 0.0)
                if energy > 3.5:  # Only high-energy sinks are real attractors
                    attractor_candidates.append((sym, sms, energy * 0.5))

        # Criterion 1: field_role indicates attractor
            if getattr(sms, "field_role", None) == "attractor":
                attractor_candidates.append((sym, sms, 3.0))  # weight=3 (highest)
                continue

            # Criterion 2: high in-degree / low out-degree (sink behavior)
            in_deg = len(self._in_neighbors.get(sym, []))
            out_deg = len(self._adjacency.get(sym, []))

            if in_deg > 0 and out_deg <= 2:
                # Strong sink behavior
                score = in_deg / (out_deg + 1)
                if sms.role.type == "sink":
                    score += 1.0
                attractor_candidates.append((sym, sms, score))

            # Criterion 3: terminal symbols with persistence semantics
            if sms.role.type == "sink" and in_deg >= 2:
                energy = 0.0
                if sms.energy:
                    energy = sms.energy.get("total", 0.0)
                if energy > 3.5:  # Only high-energy sinks are real attractors
                    attractor_candidates.append((sym, sms, energy * 0.5))

        # Deduplicate candidates (same symbol can appear from multiple criteria)
        seen: Dict[str, tuple] = {}  # symbol → (sms, best_score)
        for sym, sms, score in attractor_candidates:
            if sym not in seen or score > seen[sym][1]:
                seen[sym] = (sms, score)
        attractor_candidates = [(sym, sms, score) for sym, (sms, score) in seen.items()]

        # Sort by attractor score
        attractor_candidates.sort(key=lambda x: x[2], reverse=True)

        # Filter out dunder methods and very short generic names
        def is_attractor_valid(sym: str) -> bool:
            if self._is_generic_symbol(sym):
                return False
            name = sym.replace("sym::", "")
            # Exclude dunder methods (framework hooks, not business logic)
            if name.startswith("__") and name.endswith("__"):
                return False
            # Exclude single-letter or very short names
            if len(name) <= 3:
                return False
            return True

        # Return top attractors that pass validation (max 5 per community)
        result = []
        for sym, sms, score in attractor_candidates:
            if len(result) >= 5:
                break
            if is_attractor_valid(sym):
                result.append(sym)

        return result

    def _build_navigation_hint(
        self,
        archetype: TopologicalArchetype,
        structure,
        size: int,
    ) -> "NavigationHint":
        """Build navigation hint from archetype and structure."""
        from . import NavigationHint

        ARCHETYPE_HINTS = {
            TopologicalArchetype.HUB: (
                "expand_outward",
                "High fan-out hub: orchestration layer, start from top entry points and expand outward to callers",
                ["broad scope, may need filtering by intent"],
            ),
            TopologicalArchetype.SINK: (
                "converge_inward",
                "High fan-in sink: terminal layer, often I/O or persistence, navigate upstream first then converge",
                ["may be volatile I/O boundary"],
            ),
            TopologicalArchetype.CHAIN: (
                "traverse",
                "Balanced chain: transitional layer, traverse sequentially following the call chain",
                ["long chains may lose context"],
            ),
            TopologicalArchetype.FANOUT: (
                "expand_outward",
                "Leaf-dominated fanout: utility layer, expand outward from leaf entry points",
                ["many small functions, may need targeted intent"],
            ),
            TopologicalArchetype.TRANSITIONAL: (
                "traverse",
                "Mixed transitional: structural boundary zone, traverse carefully checking context",
                ["may span multiple concerns"],
            ),
        }

        mode, hint, risks = ARCHETYPE_HINTS.get(
            archetype,
            ("traverse", "Mixed structure: use standard traversal", ["unknown structure"]),
        )

        return NavigationHint(
            suggested_mode=mode,
            landing_hint=hint,
            risks=risks,
        )

    def get_basin_map(self) -> Dict[str, int]:
        """Get symbol → community_id mapping (for inter-center pass).

        Kept for backwards compatibility with pass5_inter_center_graph.py.
        """
        return dict(self._communities)

    def get_structural_clusters(self) -> List[StructuralCluster]:
        """Get detected structural clusters from SCG analysis."""
        return self._structural_clusters

    def get_coupled_centers(self) -> List[CoupledCenters]:
        """Get coupled center pairs from SCG analysis."""
        return self._coupled_centers

    def _fallback_seeding(
        self,
        symbol_map: Dict[str, SymbolManifoldState],
    ) -> List[CommunitySeed]:
        """Fallback: seed communities based on high centrality + energy diversity.

        Used when no seeds found via _seed_communities.
        Picks diverse symbols by energy bands.
        """
        seeds = []
        community_id = 0

        # Sort by centrality descending, take top 10
        sorted_symbols = sorted(
            symbol_map.items(),
            key=lambda x: x[1].topology.centrality if x[1].topology else 0.0,
            reverse=True,
        )

        for symbol_id, sms in sorted_symbols[:10]:
            if not sms.topology:
                continue
            if self._is_generic_symbol(symbol_id):
                continue
            out_deg = len(self._adjacency.get(symbol_id, []))
            # Only include if not too connected (avoid hub pollution)
            if out_deg > 0 and out_deg < 30:
                energy = 0.0
                if sms.energy:
                    energy = sms.energy.get("total", 0.0)
                seeds.append(CommunitySeed(
                    symbol_id=symbol_id,
                    community_id=community_id,
                    role_type=sms.role.type,
                    energy=energy,
                    centrality=sms.topology.centrality,
                ))
                community_id += 1

        return seeds


# Phase 3.7: Structural Coupling Graph (SCG)

def get_module_path(symbol_id: str) -> str:
    """Extract physical module path from symbol ID."""
    if "::" not in symbol_id:
        return "unknown"
    parts = symbol_id.split("::")
    if len(parts) < 2:
        return "unknown"
    # sym::quro.tda.phase4.cli::main → quro.tda.phase4
    module_path = parts[1].rsplit(".", 1)[0] if "." in parts[1] else parts[1]
    return module_path


def _bfs_reachable(
    start: str,
    adjacency: Dict[str, List[str]],
    max_hops: int,
    visited: Optional[Set[str]] = None,
) -> Set[str]:
    """BFS reachability from start node within max_hops."""
    if visited is None:
        visited = set()
    queue = deque([(start, 0)])
    reachable = set()

    while queue:
        node, depth = queue.popleft()
        if node in visited or depth > max_hops:
            continue
        visited.add(node)
        reachable.add(node)

        for neighbor in adjacency.get(node, []):
            if neighbor not in visited:
                queue.append((neighbor, depth + 1))

    return reachable


def build_coupling_graph(
    adjacency: Dict[str, List[str]],
    symbol_map: Dict[str, SymbolManifoldState],
) -> nx.Graph:
    """Build undirected coupling graph.

    Two symbols are coupled if they share downstream sinks within COUPLING_MAX_HOPS.
    Edge weight = number of shared sinks.

    Algorithm (bitmask intersection):
      The naive approach computes `len(reach(a) & reach(b))` as a Python set
      intersection for each of C(N,2) symbol pairs. That intersection is the
      dominant cost (~25s on a 3.3k-symbol graph).

      We instead encode each symbol's reachability set as a single Python int
      bitmask (one bit per symbol index) and compute the shared-sink count as
      `(bits_a & bits_b).bit_count()`. The bitwise AND and popcount run in C
      over a fixed-width big integer, making each pair ~15-20x cheaper while
      producing identical counts.

      The `shared_sinks` set per edge is NOT materialized here -- it is only
      needed by a small subset of edges (those inside detected structural
      clusters and inter-center pairs). The reachability sets are attached as
      the graph attribute `reachable` so downstream consumers can reconstruct
      `shared_sinks = reach[a] & reach[b]` lazily for just the edges they read.
    """
    import networkx as nx
    from itertools import combinations

    G = nx.Graph()

    # Add all symbols as nodes
    symbols = list(symbol_map.keys())
    G.add_nodes_from(symbols)

    # Compute reachable sets (one BFS per node) and index them for bitmasks
    idx = {s: i for i, s in enumerate(symbols)}
    reachable_cache: Dict[str, Set[str]] = {}
    for sym in symbols:
        reachable_cache[sym] = _bfs_reachable(sym, adjacency, COUPLING_MAX_HOPS)

    # Encode each reachability set as an integer bitmask
    reach_bits: Dict[str, int] = {}
    for sym in symbols:
        bits = 0
        for tgt in reachable_cache[sym]:
            bits |= (1 << idx[tgt])
        reach_bits[sym] = bits

    # Build coupling edges via bitmask AND + popcount (identical counts, far cheaper)
    for sym_a, sym_b in combinations(symbols, 2):
        weight = (reach_bits[sym_a] & reach_bits[sym_b]).bit_count()
        if weight >= MIN_SHARED_SINKS:
            G.add_edge(sym_a, sym_b, weight=weight)

    # Attach reachability sets so consumers can lazily reconstruct shared_sinks
    # for the edges they actually inspect (clusters / inter-center pairs).
    G.graph["reachable"] = reachable_cache

    return G


def detect_structural_clusters(
    coupling_graph: nx.Graph,
    symbol_map: Dict[str, SymbolManifoldState],
    adjacency: Dict[str, List[str]],
) -> Tuple[List[StructuralCluster], Dict[str, str]]:
    """Louvain community detection on coupling graph.

    Returns:
        Tuple of (clusters, symbol_to_cluster_mapping)
    """
    import networkx as nx
    from networkx.algorithms import community

    # Louvain clustering
    communities = community.louvain_communities(coupling_graph, weight="weight", seed=42)

    clusters = []
    symbol_to_cluster: Dict[str, str] = {}

    for cluster_id, members in enumerate(communities):
        if len(members) < MIN_SC_CLUSTER_SIZE:
            continue

        cluster_id_str = f"SC{cluster_id}"

        # Track cluster membership
        for sym in members:
            symbol_to_cluster[sym] = cluster_id_str

        # Compute cluster metrics
        subgraph = coupling_graph.subgraph(members)
        internal_edges = subgraph.number_of_edges()
        possible_edges = len(members) * (len(members) - 1) / 2
        density = internal_edges / possible_edges if possible_edges > 0 else 0.0

        # Identify shared sinks
        # build_coupling_graph stores reachability as a graph attribute and does
        # not materialize shared_sinks per edge; reconstruct it lazily here for
        # just the edges inside this (small) cluster subgraph.
        reachable = coupling_graph.graph.get("reachable")
        all_shared_sinks: Set[str] = set()
        for u, v, data in subgraph.edges(data=True):
            if "shared_sinks" in data:
                all_shared_sinks.update(data["shared_sinks"])
            elif reachable is not None:
                all_shared_sinks.update(reachable.get(u, set()) & reachable.get(v, set()))

        # Identify hub symbols (high degree within cluster)
        degrees = dict(subgraph.degree())
        hub_symbols = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:3]
        hub_symbols = [sym for sym, deg in hub_symbols]

        # Physical modules
        physical_modules = set(get_module_path(sym) for sym in members)
        is_cross_module = len(physical_modules) > 1

        # Classify archetype
        if density >= TIGHT_COUPLING_DENSITY:
            archetype = StructuralArchetype.TIGHT_COUPLING
        elif len(all_shared_sinks) >= 5:
            archetype = StructuralArchetype.FLOW_CONVERGENT
        elif len(hub_symbols) > 0 and degrees.get(hub_symbols[0], 0) > len(members) * 0.5:
            archetype = StructuralArchetype.RADIATION
        else:
            archetype = StructuralArchetype.LOOSE_COUPLING

        clusters.append(StructuralCluster(
            id=cluster_id_str,
            size=len(members),
            archetype=archetype,
            density=round(density, 3),
            internal_edges=internal_edges,
            shared_sinks=list(all_shared_sinks)[:10],
            hub_symbols=hub_symbols,
            physical_modules=list(physical_modules),
            is_cross_module=is_cross_module,
        ))

    return clusters, symbol_to_cluster


def _get_symbol_center_mapping(
    centers: List[SemanticCenter],
    symbol_map: Dict[str, SymbolManifoldState],
) -> Dict[str, str]:
    """Map symbol_id → center_id."""
    mapping = {}
    for center in centers:
        # Get all symbols in this center
        center_id = center.id
        for sym_id in symbol_map.keys():
            sms = symbol_map[sym_id]
            if hasattr(sms, "basin_id") and sms.basin_id == center_id:
                mapping[sym_id] = center_id
    return mapping


def _get_cluster_members(
    cluster: StructuralCluster,
    coupling_graph: nx.Graph,
) -> Set[str]:
    """Get all symbol IDs in a structural cluster."""
    # This is a helper - in practice we need to track cluster membership
    # For now, return empty set (will be populated during detection)
    return set()


def _assign_centers_to_clusters(
    centers: List[SemanticCenter],
    clusters: List[StructuralCluster],
    symbol_map: Dict[str, SymbolManifoldState],
    symbol_to_cluster: Dict[str, str],
    communities: Dict[str, str],
) -> Dict[str, Tuple[str, float]]:
    """Assign each center to its dominant structural cluster.

    Args:
        centers: List of semantic centers
        clusters: List of structural clusters
        symbol_map: Symbol manifold states
        symbol_to_cluster: Symbol → structural cluster mapping
        communities: Symbol → center ID mapping (from self._communities)

    Returns: center_id → (cluster_id, purity_score)
    """
    assignments = {}
    for center in centers:
        center_id = center.id

        # Get symbols in this center using communities mapping
        center_symbols = [sym_id for sym_id, cid in communities.items() if cid == center_id]

        if not center_symbols:
            continue

        # Count cluster membership
        cluster_counts: Dict[str, int] = {}
        for sym in center_symbols:
            cluster_id = symbol_to_cluster.get(sym)
            if cluster_id:
                cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

        if cluster_counts:
            dominant_cluster = max(cluster_counts.items(), key=lambda x: x[1])
            purity = dominant_cluster[1] / len(center_symbols)
            assignments[center.id] = (dominant_cluster[0], round(purity, 3))

    return assignments


def compute_inter_center_coupling(
    centers: List[SemanticCenter],
    clusters: List[StructuralCluster],
    coupling_graph: nx.Graph,
    symbol_map: Dict[str, SymbolManifoldState],
    symbol_to_cluster: Dict[str, str],
    communities: Dict[str, str],
) -> List[CoupledCenters]:
    """Compute coupling between semantic centers via structural clusters.

    Args:
        centers: List of semantic centers
        clusters: List of structural clusters
        coupling_graph: Coupling graph
        symbol_map: Symbol manifold states
        symbol_to_cluster: Symbol → structural cluster mapping
        communities: Symbol → center ID mapping (from self._communities)
    """
    from itertools import combinations

    # Reachability sets for lazy shared_sinks reconstruction (see build_coupling_graph)
    reachable = coupling_graph.graph.get("reachable")

    # Build center → symbols mapping using communities
    center_symbols: Dict[str, Set[str]] = {}
    for center in centers:
        center_id = center.id
        symbols = set(sym_id for sym_id, cid in communities.items() if cid == center_id)
        center_symbols[center_id] = symbols

    coupled = []
    for center_a, center_b in combinations(centers, 2):
        symbols_a = center_symbols.get(center_a.id, set())
        symbols_b = center_symbols.get(center_b.id, set())

        if not symbols_a or not symbols_b:
            continue

        # Count coupling edges between centers
        coupling_edges = 0
        bridge_symbols = set()
        shared_sinks_set: Set[str] = set()

        for sym_a in symbols_a:
            for sym_b in symbols_b:
                if coupling_graph.has_edge(sym_a, sym_b):
                    coupling_edges += 1
                    bridge_symbols.add(sym_a)
                    bridge_symbols.add(sym_b)
                    edge_data = coupling_graph.get_edge_data(sym_a, sym_b)
                    if edge_data:
                        if "shared_sinks" in edge_data:
                            shared_sinks_set.update(edge_data["shared_sinks"])
                        elif reachable is not None:
                            shared_sinks_set.update(
                                reachable.get(sym_a, set()) & reachable.get(sym_b, set())
                            )

        if coupling_edges == 0:
            continue

        # Coupling score: normalized by center sizes
        max_possible = min(len(symbols_a), len(symbols_b))
        coupling_score = coupling_edges / max_possible if max_possible > 0 else 0.0

        if coupling_score < MIN_COUPLING_SCORE:
            continue

        explanation = _build_coupling_explanation(
            center_a, center_b, list(bridge_symbols)[:5], list(shared_sinks_set)[:5]
        )

        coupled.append(CoupledCenters(
            center_a=center_a.id,
            center_b=center_b.id,
            coupling_score=round(coupling_score, 3),
            shared_sinks=list(shared_sinks_set)[:10],
            bridge_symbols=list(bridge_symbols)[:10],
            explanation=explanation,
        ))

    return coupled


def _build_coupling_explanation(
    center_a: SemanticCenter,
    center_b: SemanticCenter,
    bridge_symbols: List[str],
    shared_sinks: List[str],
) -> str:
    """Build human-readable coupling explanation."""
    return (
        f"Centers '{center_a.id}' and '{center_b.id}' are structurally coupled "
        f"via {len(bridge_symbols)} bridge symbols flowing to {len(shared_sinks)} shared sinks"
    )


def enrich_centers_with_scg(
    centers: List[SemanticCenter],
    clusters: List[StructuralCluster],
    coupled_centers: List[CoupledCenters],
    coupling_graph: nx.Graph,
    symbol_map: Dict[str, SymbolManifoldState],
    symbol_to_cluster: Dict[str, str],
    communities: Dict[str, str],
) -> List[SemanticCenterSCG]:
    """Enrich semantic centers with structural coupling information.

    Args:
        centers: List of semantic centers
        clusters: List of structural clusters
        coupled_centers: List of coupled center pairs
        coupling_graph: Coupling graph
        symbol_map: Symbol manifold states
        symbol_to_cluster: Symbol → structural cluster mapping
        communities: Symbol → center ID mapping (from self._communities)
    """
    # Assign centers to clusters
    center_assignments = _assign_centers_to_clusters(
        centers, clusters, symbol_map, symbol_to_cluster, communities
    )

    # Build coupled centers lookup
    coupled_lookup: Dict[str, List[CoupledCenters]] = {}
    for cc in coupled_centers:
        coupled_lookup.setdefault(cc.center_a, []).append(cc)
        coupled_lookup.setdefault(cc.center_b, []).append(cc)

    enriched = []
    for center in centers:
        center_id = center.id
        cluster_info = center_assignments.get(center_id)

        if cluster_info:
            cluster_id, purity = cluster_info
            cluster = next((c for c in clusters if c.id == cluster_id), None)
            archetype = cluster.archetype if cluster else StructuralArchetype.LOOSE_COUPLING
        else:
            cluster_id = None
            purity = 0.0
            archetype = StructuralArchetype.LOOSE_COUPLING

        # Get coupled centers
        center_coupled = coupled_lookup.get(center_id, [])

        # Get shared sinks from cluster
        cluster = next((c for c in clusters if c.id == cluster_id), None) if cluster_id else None
        shared_sinks = cluster.shared_sinks if cluster else []

        # Check if cross-module
        is_cross_module = cluster.is_cross_module if cluster else False

        enriched.append(SemanticCenterSCG(
            id=center.id,
            size=center.size,
            density=center.density,
            structure=center.structure,
            topology=center.topology,
            navigation=center.navigation,
            stable_id=center.stable_id,
            members_hash=center.members_hash,
            structural_cluster_id=cluster_id,
            structural_purity=purity,
            coupling_archetype=archetype,
            coupled_centers=center_coupled,
            shared_sinks=shared_sinks,
            is_cross_module=is_cross_module,
        ))

    return enriched
