"""Pass 3: Asymmetric Edge Weighting

@module quro.tda.phase2_5.pass3_edge_weighting
@intent Assign asymmetric weights to edges based on relationship type and data flow.

        Composition (class→method): 0.9 (tight coupling)
        Inheritance (parent→child): 0.85 (strong coupling)
        Dependency (module→module): 0.5 (medium coupling)
        Utility call (business→utility): 0.3 (weak coupling)
        Data flow (complex object): 0.7 (high dissipation)
        Data flow (primitive): 0.4 (low dissipation)
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


# Edge weight constants
EDGE_WEIGHTS = {
    "composition": 0.9,      # Class → Method
    "inheritance": 0.85,     # Parent → Child
    "dependency": 0.5,       # Module → Module
    "utility_call": 0.3,     # Business → Utility
    "data_flow_complex": 0.7,  # Passing DTO/Class
    "data_flow_simple": 0.4,   # Passing primitive
    "default": 0.5,          # Unknown relationship
}


@dataclass(frozen=True)
class EdgeWeight:
    """Asymmetric edge weight.

    Attributes:
        src: Source symbol ID
        dst: Target symbol ID
        edge_type: Edge type (composition, dependency, etc.)
        weight: Asymmetric weight [0, 1]
        dissipation: Energy dissipation [0, 1]
    """
    src: str
    dst: str
    edge_type: str
    weight: float
    dissipation: float


def classify_edge_type(src_id: str, dst_id: str, src_metadata: Dict, dst_metadata: Dict) -> str:
    """Classify edge relationship type.

    Args:
        src_id: Source symbol ID
        dst_id: Target symbol ID
        src_metadata: Source symbol metadata
        dst_metadata: Target symbol metadata

    Returns:
        Edge type string
    """
    # Check for composition (class → method)
    src_kind = src_metadata.get("kind", "")
    dst_kind = dst_metadata.get("kind", "")

    if src_kind == "class" and dst_kind == "method":
        return "composition"

    # Check for inheritance
    if "inherits" in src_metadata or "parent" in src_metadata:
        return "inheritance"

    # Check for utility call (business logic → utility)
    src_intent = src_metadata.get("intent", "")
    dst_intent = dst_metadata.get("intent", "")

    if "business" in src_intent.lower() and "utility" in dst_intent.lower():
        return "utility_call"

    # Default to dependency
    return "dependency"


def estimate_data_complexity(edge_metadata: Dict) -> str:
    """Estimate data flow complexity.

    Args:
        edge_metadata: Edge metadata

    Returns:
        "complex" or "simple"
    """
    # Check if edge passes complex data
    data_type = edge_metadata.get("data_type", "")

    if any(keyword in data_type.lower() for keyword in ["class", "dto", "object", "dict", "list"]):
        return "complex"
    else:
        return "simple"


def compute_asymmetric_weights(
    registry_db_path: Path,
    output_path: Path,
) -> Dict[str, EdgeWeight]:
    """Compute asymmetric weights for all edges.

    Args:
        registry_db_path: Path to registry.db
        output_path: Output path for edge_weights.json

    Returns:
        Dict mapping (src, dst) → EdgeWeight
    """
    logger.info("Computing asymmetric edge weights from %s", registry_db_path)

    # Load registry
    from index_builder.adapters.sqlite import SQLiteRegistryAdapter
    adapter = SQLiteRegistryAdapter(db_path=registry_db_path)
    all_nodes = adapter.get_all_nodes()

    # Build metadata map
    metadata_map = {node.id: node.metadata or {} for node in all_nodes}

    # Process all edges
    edge_weights: Dict[str, EdgeWeight] = {}
    total_edges = 0

    for node in all_nodes:
        src_id = node.id
        src_metadata = metadata_map.get(src_id, {})

        edges = adapter.get_edges_from(src_id)
        total_edges += len(edges)

        for edge in edges:
            dst_id = edge.dst
            dst_metadata = metadata_map.get(dst_id, {})

            # Classify edge type
            edge_type = classify_edge_type(src_id, dst_id, src_metadata, dst_metadata)

            # Get base weight
            base_weight = EDGE_WEIGHTS.get(edge_type, EDGE_WEIGHTS["default"])

            # Estimate data complexity (for dissipation)
            edge_metadata = edge.metadata or {}
            data_complexity = estimate_data_complexity(edge_metadata)

            if data_complexity == "complex":
                dissipation = 0.7
            else:
                dissipation = 0.4

            # Store edge weight
            edge_key = f"{src_id}→{dst_id}"
            edge_weights[edge_key] = EdgeWeight(
                src=src_id,
                dst=dst_id,
                edge_type=edge_type,
                weight=base_weight,
                dissipation=dissipation,
            )

    # Statistics
    edge_type_counts = {}
    for ew in edge_weights.values():
        edge_type_counts[ew.edge_type] = edge_type_counts.get(ew.edge_type, 0) + 1

    logger.info(
        "Computed asymmetric weights for %d edges (total: %d)",
        len(edge_weights), total_edges,
    )
    logger.info("Edge type distribution: %s", edge_type_counts)

    # Write to file
    output_data = {
        "metadata": {
            "source": "registry_graph",
            "total_edges": len(edge_weights),
            "edge_type_counts": edge_type_counts,
        },
        "weights": {
            edge_key: {
                "src": ew.src,
                "dst": ew.dst,
                "edge_type": ew.edge_type,
                "weight": ew.weight,
                "dissipation": ew.dissipation,
            }
            for edge_key, ew in edge_weights.items()
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info("Wrote edge weights to %s", output_path)
    return edge_weights
