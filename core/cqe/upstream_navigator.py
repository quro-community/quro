"""Upstream Navigator — Controlled Backward Navigation

@module quro.core.cqe.upstream_navigator
@intent Provide controlled backward navigation for escape from sink nodes and flat fields.

       Uses anisotropic field model where backward tension is a separate scalar signal,
       never merged with forward directional vector.

       Key constraints:
       - max_depth ≤ 2 (prevent explosion)
       - Backward weight ≤ 0.15 in scoring (light injection)
       - Only activates when forward navigation fails
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpstreamSource:
    """Upstream source candidate for escape.

    Attributes:
        symbol: Source symbol ID
        tension: Backward tension [0, 1]
        distance: Hop distance from start node
        source_type: "direct_caller" or "indirect"
        forward_magnitude: Forward field strength of source
        score: Composite escape score
    """
    symbol: str
    tension: float
    distance: int
    source_type: str
    forward_magnitude: float
    score: float


@dataclass(frozen=True)
class EscapeResult:
    """Result of escape_sink operation.

    Attributes:
        escape_to: Target symbol to escape to
        confidence: Escape confidence [0, 1]
        reason: Classification of escape reason
        upstream_sources: All candidates considered
    """
    escape_to: str
    confidence: float
    reason: str
    upstream_sources: List[UpstreamSource]


class UpstreamNavigator:
    """Controlled backward navigation for escape.

    Provides two main operations:
    1. find_upstream_sources: Limited BFS backward traversal
    2. escape_sink: Smart escape policy when forward navigation fails

    Invariant: Backward signal never merged with forward vector.
    """

    def __init__(
        self,
        anisotropic_fields_path: Path,
        registry_db_path: Path
    ):
        """Initialize upstream navigator.

        Args:
            anisotropic_fields_path: Path to anisotropic_fields.jsonl
            registry_db_path: Path to registry.db
        """
        self.anisotropic_fields_path = anisotropic_fields_path
        self.registry_db_path = registry_db_path

        # Load anisotropic fields into memory
        self.fields = self._load_anisotropic_fields()

        logger.info(
            "UpstreamNavigator initialized with %d fields",
            len(self.fields)
        )

    def _load_anisotropic_fields(self) -> Dict[str, dict]:
        """Load anisotropic fields from JSONL file.

        Returns:
            Dict mapping symbol → field data
        """
        fields = {}

        with open(self.anisotropic_fields_path, "r") as f:
            for line in f:
                field = json.loads(line)
                symbol = field["symbol"]
                fields[symbol] = field

        return fields

    def _query_incoming_edges(self, symbol: str) -> List[tuple[str, float]]:
        """Query incoming edges from registry database.

        Args:
            symbol: Target symbol ID

        Returns:
            List of (source_symbol, edge_weight) tuples
        """
        import sqlite3

        conn = sqlite3.connect(self.registry_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT src, weight
            FROM edges
            WHERE dst = ?
            ORDER BY weight DESC
            """,
            (symbol,)
        )

        edges = [(row["src"], row["weight"]) for row in cursor.fetchall()]
        conn.close()

        return edges

    def _resolve_symbol(self, symbol: str) -> str:
        """Resolve symbol to short name if needed.

        Handles both short names (sym::CQEIndexPipeline) and full hash-suffixed names
        (sym::quro_sovereign.cqe_index_pipeline::CQEIndexPipeline::3485c89331451f15).

        Args:
            symbol: Symbol ID (short or full)

        Returns:
            Short symbol name that exists in fields
        """
        # If symbol exists in fields as-is, return it
        if symbol in self.fields:
            return symbol

        # Try to extract short name from full hash-suffixed ID
        # Format: sym::module.path::ClassName::hash
        # Extract: sym::ClassName
        if "::" in symbol:
            parts = symbol.split("::")
            if len(parts) >= 3:
                # Try sym::ClassName
                short_name = f"sym::{parts[-2]}"
                if short_name in self.fields:
                    return short_name

        # Return original if no match found
        return symbol

    def find_upstream_sources(
        self,
        node: str,
        top_k: int = 5,
        max_depth: int = 2
    ) -> List[UpstreamSource]:
        """Find upstream sources via limited BFS.

        CRITICAL: max_depth ≤ 2 to prevent explosion.

        Args:
            node: Starting node ID (short or full hash-suffixed)
            top_k: Number of top sources to return
            max_depth: Maximum traversal depth (hard limit: 2)

        Returns:
            List of UpstreamSource candidates, sorted by score
        """
        # Resolve to short name for field lookup
        resolved_node = self._resolve_symbol(node)

        # Enforce hard depth limit
        if max_depth > 2:
            logger.warning(
                "max_depth=%d exceeds limit, clamping to 2",
                max_depth
            )
            max_depth = 2

        candidates = []
        visited = {resolved_node}
        queue = [(resolved_node, 0)]

        while queue:
            current, depth = queue.pop(0)

            if depth >= max_depth:
                continue

            # Get incoming edges
            incoming = self._query_incoming_edges(current)

            for src, edge_weight in incoming:
                if src in visited:
                    continue

                visited.add(src)

                # Get source field data
                src_field = self.fields.get(src, {})
                forward_mag = src_field.get("forward_magnitude", 0.0)
                backward_ten = src_field.get("backward_tension", 0.0)

                # Compute score: edge_weight × forward_magnitude × exponential_decay
                # Use strict exponential decay: 0.5^distance
                # This ensures direct callers (distance=1) always dominate indirect (distance≥2)
                # unless the indirect is a true system-level hub
                distance = depth + 1
                exponential_decay = 0.5 ** distance
                score = edge_weight * forward_mag * exponential_decay

                # Classify source type
                source_type = "direct_caller" if depth == 0 else "indirect"

                candidates.append(
                    UpstreamSource(
                        symbol=src,
                        tension=backward_ten,
                        distance=depth + 1,
                        source_type=source_type,
                        forward_magnitude=forward_mag,
                        score=score
                    )
                )

                # Enqueue for next level
                queue.append((src, depth + 1))

        # Sort by score and return top-k
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[:top_k]

    def escape_sink(self, node: str) -> EscapeResult:
        """Smart escape policy for sink nodes.

        Scoring formula:
        - Backward tension: 0.6 (primary: upstream pull)
        - Forward magnitude: 0.3 (secondary: escape viability)
        - Source diversity: 0.1 (tertiary: richness)

        Args:
            node: Sink node to escape from (short or full hash-suffixed)

        Returns:
            EscapeResult with best escape target
        """
        # Resolve to short name for field lookup
        resolved_node = self._resolve_symbol(node)

        # Find upstream sources
        upstream = self.find_upstream_sources(resolved_node, top_k=5, max_depth=2)

        if not upstream:
            # No escape routes found
            return EscapeResult(
                escape_to=node,
                confidence=0.0,
                reason="no_upstream_sources",
                upstream_sources=[]
            )

        # Score each candidate
        def escape_score(src: UpstreamSource) -> float:
            # Get source diversity from field data
            src_field = self.fields.get(src.symbol, {})
            diversity = src_field.get("source_diversity", 0.0)

            return (
                src.tension * 0.6 +           # Primary: upstream pull
                src.forward_magnitude * 0.3 + # Secondary: escape viability
                diversity * 0.1               # Tertiary: richness
            )

        # Find best candidate
        scored = [(src, escape_score(src)) for src in upstream]
        scored.sort(key=lambda x: x[1], reverse=True)

        best_src, best_score = scored[0]

        # Classify escape reason
        reason = self._classify_escape_reason(best_src)

        return EscapeResult(
            escape_to=best_src.symbol,
            confidence=best_score,
            reason=reason,
            upstream_sources=upstream
        )

    def _classify_escape_reason(self, src: UpstreamSource) -> str:
        """Classify escape reason based on source characteristics.

        Args:
            src: Upstream source

        Returns:
            Reason string
        """
        if src.tension > 0.7 and src.forward_magnitude > 0.7:
            return "high_tension_high_forward"
        elif src.tension > 0.7:
            return "high_tension"
        elif src.forward_magnitude > 0.7:
            return "high_forward"
        else:
            return "best_available"

    def classify_node_role(self, node: str) -> str:
        """Classify node role based on forward/backward matrix.

        Args:
            node: Node ID (short or full hash-suffixed)

        Returns:
            Role: CORE_ATTRACTOR, EMITTER, CONVERTER, SINK, or TRANSIENT
        """
        # Resolve to short name for field lookup
        resolved_node = self._resolve_symbol(node)
        field = self.fields.get(resolved_node, {})
        forward_mag = field.get("forward_magnitude", 0.0)
        backward_ten = field.get("backward_tension", 0.0)
        in_degree = field.get("in_degree", 0)
        out_degree = field.get("out_degree", 0)

        # CONVERTER: high fan-in + high fan-out (entropy reducers)
        if in_degree > 5 and out_degree > 5:
            return "CONVERTER"

        # CORE_ATTRACTOR: high forward + high backward
        if forward_mag > 0.7 and backward_ten > 0.7:
            return "CORE_ATTRACTOR"
        # EMITTER: high forward, low backward
        elif forward_mag > 0.7 and backward_ten < 0.3:
            return "EMITTER"
        # SINK: low forward, high backward
        elif forward_mag < 0.3 and backward_ten > 0.7:
            return "SINK"
        else:
            return "TRANSIENT"

    def get_field_data(self, node: str) -> Optional[dict]:
        """Get anisotropic field data for a node.

        Args:
            node: Node ID (short or full hash-suffixed)

        Returns:
            Field data dict or None if not found
        """
        # Resolve to short name for field lookup
        resolved_node = self._resolve_symbol(node)
        return self.fields.get(resolved_node)
