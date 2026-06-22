"""CQE Output Refiner Protocol Implementation

@module quro.core.cqe.refiner
@intent Transform raw CQE results into LLM-friendly, structured context without context explosion
@constraint Must strictly respect configured token budgets
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from core.cqe.types import CQEResult, CQERefinedResult, CQERefinerProtocol
from core.cqe.scoring import SemanticScorer, SemanticScore

class DefaultCQERefiner(CQERefinerProtocol):
    """
    Default refiner implementation that separates CQE outputs into primary and secondary 
    structural categories to prevent AI confusion and context explosion.
    """
    
    def __init__(
        self,
        node_metadata_fetcher: Callable[[str], Dict[str, Any]],
        max_tokens: int = 4000,
        bytes_per_token_est: float = 4.0
    ):
        """
        Args:
            node_metadata_fetcher: Formats node ID into its full metadata dict/object mapping.
            max_tokens: Total token budget for the result output list. 
            bytes_per_token_est: Heuristic bytes-to-token ratio for estimation.
        """
        self.fetcher = node_metadata_fetcher
        self.max_tokens = max_tokens
        self.bytes_per_token_est = bytes_per_token_est

    def refine(self, result: CQEResult, entry_token: str) -> CQERefinedResult:
        """
        Refine the raw max_weights into categorized nodes sorted by weight.
        """
        refined = CQERefinedResult()
        
        # Sort by weight globally
        sorted_items = sorted(
            result.max_weights.items(),
            key=lambda item: item[1],
            reverse=True
        )
        
        current_tokens = 0
        
        for node_id, weight in sorted_items:
            # Skip the query entry token itself to avoid echoing what the AI likely already knows
            if node_id == entry_token:
                continue
                
            metadata = self.fetcher(node_id) or {}
            
            # Extract tags/intent
            tags = metadata.get("tags", [])
            intent = metadata.get("metadata", {}).get("intent", "semantic")
            kind = metadata.get("metadata", {}).get("kind", "unknown")
            is_noisy = metadata.get("metadata", {}).get("is_noisy", False)
            
            # We don't want explicitly noisy or hidden nodes unless they somehow had massive weight
            if is_noisy and weight < 0.8:
                continue

            node_repr = {
                "id": node_id,
                "weight": round(weight, 4),
                "kind": kind,
                "file_path": metadata.get("metadata", {}).get("file_path", ""),
            }
            
            # Categorize
            is_structural = "structural" in tags or intent == "structural"
            is_primary = False
            
            if is_structural:
                # Primary structure rules: classes, interfaces, core modules, high weight
                if kind in ("class", "interface", "protocol", "module") or weight >= 0.8:
                    is_primary = True
            
            # Fetch payload (signature/docstring) ONLY for primary candidates to prevent blowing up context
            payload_str = ""
            if is_primary:
                sig = metadata.get("metadata", {}).get("signature", "")
                if sig:
                    node_repr["signature"] = sig
                    payload_str += sig
                refined.primary_structural.append(node_repr)
            elif is_structural:
                # Secondary structures get stripped of payload
                refined.secondary_structural.append(node_repr)
            else:
                refined.related_concepts.append(node_repr)
                
            # Estimate token usage
            node_str = str(node_repr)
            tokens_est = int(len(node_str) / self.bytes_per_token_est)
            
            if current_tokens + tokens_est > self.max_tokens:
                refined.truncated = True
                break
                
            current_tokens += tokens_est
            
        refined.strict_token_budget_est = current_tokens
        refined.metadata["nodes_processed"] = len(refined.primary_structural) + len(refined.secondary_structural) + len(refined.related_concepts)
        refined.metadata["tau"] = min(result.max_weights.values()) if result.max_weights else 0
        
        refined.advisory = (
            f"CQE extracted {refined.metadata['nodes_processed']} relevant nodes tightly coupled to '{entry_token}'. "
            "Primary structural nodes include full signatures. Focus your architectural understanding there. "
            "Secondary nodes are listed by reference only. Do not blindly hallucinate their implementations if you need them—call tool to read."
        )

        return refined


@dataclass
class IntentGroup:
    """Group of nodes with the same intent."""
    intent: str
    nodes: List[Dict[str, Any]]
    total_score: float


class SemanticCQERefiner(CQERefinerProtocol):
    """Semantic-aware refiner with intent grouping and scoring.

    Leverages Phase 1 (topology) and Phase 2 (semantic) enricher tags to:
    - Prioritize architecturally significant nodes (controllers, services)
    - Demote noisy/ambiguous symbols
    - Group results by intent for better LLM reasoning
    - Optimize token budgets for maximum semantic density
    - Expose symbol aliases for discoverability
    """

    def __init__(
        self,
        node_metadata_fetcher: Callable[[str], Dict[str, Any]],
        max_tokens: int = 4000,
        bytes_per_token_est: float = 4.0,
        max_nodes_per_intent: int = 3,
        alias_fetcher: Optional[Callable[[str], List[Dict[str, str]]]] = None,
    ):
        """Initialize semantic refiner.

        Args:
            node_metadata_fetcher: Formats node ID into its full metadata dict/object mapping.
            max_tokens: Total token budget for the result output list.
            bytes_per_token_est: Heuristic bytes-to-token ratio for estimation.
            max_nodes_per_intent: Maximum nodes to include per intent group.
            alias_fetcher: Optional function to fetch symbol aliases (duplicate implementations).
        """
        self.fetcher = node_metadata_fetcher
        self.max_tokens = max_tokens
        self.bytes_per_token_est = bytes_per_token_est
        self.max_nodes_per_intent = max_nodes_per_intent
        self.scorer = SemanticScorer()
        self.alias_fetcher = alias_fetcher

    def refine(self, result: CQEResult, entry_token: str) -> CQERefinedResult:
        """Refine with semantic scoring and intent grouping.

        Args:
            result: Raw CQE result with max_weights
            entry_token: Query entry token (excluded from results)

        Returns:
            Refined result with semantic scoring and intent grouping
        """
        # Step 1: Score all nodes
        scored_nodes = []
        for node_id, weight in result.max_weights.items():
            if node_id == entry_token:
                continue

            metadata = self.fetcher(node_id) or {}
            score = self.scorer.score(node_id, weight, metadata)

            scored_nodes.append({
                "id": node_id,
                "weight": weight,
                "score": score,
                "metadata": metadata,
            })

        # Step 2: Group by intent
        intent_groups = self._group_by_intent(scored_nodes)

        # Step 3: Allocate tokens by group priority
        refined = self._allocate_tokens(intent_groups, entry_token, result)

        return refined

    def _group_by_intent(self, scored_nodes: List[Dict]) -> List[IntentGroup]:
        """Group nodes by intent and sort within groups.

        Args:
            scored_nodes: List of nodes with scores

        Returns:
            List of intent groups sorted by total score
        """
        groups_dict = {}

        for node in scored_nodes:
            intent = node["metadata"].get("metadata", {}).get("intent", "Unknown")
            if intent not in groups_dict:
                groups_dict[intent] = []
            groups_dict[intent].append(node)

        # Sort within each group by semantic score
        groups = []
        for intent, nodes in groups_dict.items():
            sorted_nodes = sorted(nodes, key=lambda n: n["score"].total, reverse=True)
            # Limit to top N per intent
            limited_nodes = sorted_nodes[:self.max_nodes_per_intent]
            total_score = sum(n["score"].total for n in limited_nodes)
            groups.append(IntentGroup(intent, limited_nodes, total_score))

        # Sort groups by total score
        return sorted(groups, key=lambda g: g.total_score, reverse=True)

    def _allocate_tokens(self, intent_groups: List[IntentGroup], entry_token: str, result: CQEResult) -> CQERefinedResult:
        """Allocate tokens with semantic-aware payload inclusion.

        Args:
            intent_groups: Intent groups sorted by score
            entry_token: Query entry token (for advisory text)
            result: Original CQE result (for tau calculation)

        Returns:
            Refined result with token budget optimization
        """
        refined = CQERefinedResult()
        current_tokens = 0

        # Flatten all nodes and sort globally by semantic score
        all_nodes = []
        for group in intent_groups:
            all_nodes.extend(group.nodes)

        all_nodes.sort(key=lambda n: n["score"].total, reverse=True)

        for i, node in enumerate(all_nodes):
            node_id = node["id"]
            metadata = node["metadata"]
            score = node["score"]

            # Determine payload level based on rank
            if i < 5:
                payload_level = "full"
            elif i < 20:
                payload_level = "stripped"
            else:
                payload_level = "none"

            node_repr = self._build_node_repr(node_id, node, payload_level)

            # Estimate tokens
            node_str = str(node_repr)
            tokens_est = int(len(node_str) / self.bytes_per_token_est)

            if current_tokens + tokens_est > self.max_tokens:
                refined.truncated = True
                break

            # Categorize by semantic score tier
            score_total = score.total
            if score_total >= 0.8:
                refined.primary_structural.append(node_repr)
            elif score_total >= 0.5:
                refined.secondary_structural.append(node_repr)
            else:
                refined.related_concepts.append(node_repr)

            current_tokens += tokens_est

        refined.strict_token_budget_est = current_tokens
        refined.metadata["nodes_processed"] = len(refined.primary_structural) + len(refined.secondary_structural) + len(refined.related_concepts)
        refined.metadata["tau"] = min(result.max_weights.values()) if result.max_weights else 0

        # Generate intent-aware advisory
        intent_summary = self._generate_intent_summary(intent_groups)
        refined.advisory = (
            f"CQE extracted {refined.metadata['nodes_processed']} relevant nodes for '{entry_token}'. "
            f"{intent_summary} "
            "Primary nodes (score ≥0.8) include full signatures. Secondary nodes (0.5-0.8) are listed by reference. "
            "Do not hallucinate implementations—call tools to read source."
        )

        return refined

    def _build_node_repr(self, node_id: str, node: Dict, payload_level: str) -> Dict[str, Any]:
        """Build node representation with appropriate payload level.

        Args:
            node_id: Node identifier
            node: Node data with metadata and score
            payload_level: "full", "stripped", or "none"

        Returns:
            Node representation dict with optional aliases field
        """
        metadata = node["metadata"]
        score = node["score"]
        meta_dict = metadata.get("metadata", {})

        node_repr = {
            "id": node_id,
            "weight": round(node["weight"], 4),
            "semantic_score": round(score.total, 4),
            "kind": meta_dict.get("kind", "unknown"),
            "file_path": meta_dict.get("file_path", ""),
            "intent": meta_dict.get("intent", "unknown"),
        }

        # Add behavioral tags (from Phase 2 enrichers)
        tags = metadata.get("tags", [])
        if tags:
            # Filter to behavioral tags only (exclude structural/noisy)
            behavioral = [t for t in tags if t not in ("structural", "noisy", "ambiguous")]
            if behavioral:
                node_repr["behavioral_tags"] = behavioral[:5]  # Top 5

        # Add role (from Phase 2 RoleEnricher)
        role = meta_dict.get("role")
        if role:
            node_repr["role"] = role

        # Add aliases (duplicate implementations of same symbol)
        if self.alias_fetcher:
            all_matches = self.alias_fetcher(node_id)
            if all_matches:
                # Separate into true aliases (compatible signatures) and related symbols (same name, different API)
                true_aliases = []
                related_symbols = []

                for match in all_matches:
                    # Heuristic: if path contains "protocol.py", it's an interface
                    if "protocol.py" in match.get("path", "").lower():
                        continue  # Skip protocols

                    # For now, include all as aliases (let the AI decide)
                    # Future: could separate by signature similarity
                    true_aliases.append({
                        "path": match["path"],
                        "line": match["line"],
                        "kind": match["kind"],
                    })

                if true_aliases:
                    node_repr["aliases"] = true_aliases

        if payload_level == "full":
            # Include full signature
            sig = meta_dict.get("signature", "")
            if sig:
                node_repr["signature"] = sig
        elif payload_level == "stripped":
            # Include stripped signature (first line only, no docstring)
            sig = meta_dict.get("signature", "")
            if sig:
                first_line = sig.split("\n")[0]
                node_repr["signature"] = first_line
        # payload_level == "none": no signature

        return node_repr

    def _generate_intent_summary(self, intent_groups: List[IntentGroup]) -> str:
        """Generate intent summary for advisory text.

        Args:
            intent_groups: Intent groups sorted by score

        Returns:
            Human-readable intent summary
        """
        if not intent_groups:
            return "No specific intent detected."

        # Top 3 intents
        top_intents = intent_groups[:3]
        intent_counts = [(g.intent, len(g.nodes)) for g in top_intents]

        parts = []
        for intent, count in intent_counts:
            parts.append(f"{count} {intent}")

        return f"Top intents: {', '.join(parts)}."