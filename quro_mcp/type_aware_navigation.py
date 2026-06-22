"""Type-Aware Navigation Helpers

@module quro_mcp.type_aware_navigation
@intent Provide type-aware navigation logic for OOP-TDA semantic type system
@constraint Distinguishes between container nodes (Classes) and executor nodes (Methods)
"""

from typing import Dict, Any, List, Optional
from adapters.registry.types import SymbolMetadata


def get_type_aware_neighbors(
    from_symbol: str,
    registry_adapter,
    tda_api=None,
    max_candidates: int = 5
) -> Dict[str, Any]:
    """Query next best nodes with type-aware navigation.

    Args:
        from_symbol: Current symbol ID (e.g., 'sym::CQEIndexPipeline')
        registry_adapter: Registry adapter for graph queries
        tda_api: Optional TDA API for energy information
        max_candidates: Maximum number of candidates to return

    Returns:
        Dict with neighbors, node type, and explanation
    """
    # Get symbol information
    symbol_node = registry_adapter.get_node(from_symbol)

    if not symbol_node:
        return {
            "error": f"Symbol not found: {from_symbol}",
            "from_symbol": from_symbol,
        }

    # Derive semantic metadata from symbol kind
    symbol_kind = symbol_node.metadata.get("kind", "function")
    metadata = SymbolMetadata.from_symbol_kind(symbol_kind)

    # Type-aware neighbor expansion
    if metadata.is_container:
        # For Classes/Modules: Show contained executors
        neighbors = _get_contained_executors(
            from_symbol, registry_adapter, tda_api, max_candidates
        )
        explanation = (
            f"{from_symbol} is a {metadata.node_type} (container). "
            f"Showing {len(neighbors)} contained methods/functions for execution."
        )
    else:
        # For Methods/Functions: Show call graph
        neighbors = _get_execution_neighbors(
            from_symbol, registry_adapter, tda_api, max_candidates
        )
        explanation = (
            f"{from_symbol} is a {metadata.node_type} (executor). "
            f"Showing {len(neighbors)} execution neighbors."
        )

    return {
        "from_symbol": from_symbol,
        "node_type": metadata.node_type,
        "is_container": metadata.is_container,
        "is_executor": metadata.is_executor,
        "neighbors": neighbors,
        "explanation": explanation,
    }


def _get_contained_executors(
    container_id: str,
    registry_adapter,
    tda_api=None,
    max_candidates: int = 5
) -> List[Dict[str, Any]]:
    """Get executor nodes contained in a container (Class/Module).

    Args:
        container_id: Container symbol ID
        registry_adapter: Registry adapter
        tda_api: Optional TDA API for energy
        max_candidates: Max results

    Returns:
        List of neighbor dicts with symbol, kind, energy, relationship
    """
    # Get all edges and filter for CONTAINS
    all_edges = registry_adapter.get_edges_from(container_id)
    edges = [e for e in all_edges if e.kind == "contains"]

    neighbors = []
    for edge in edges:
        method_node = registry_adapter.get_node(edge.dst)
        if not method_node:
            continue

        # Get energy from TDA if available
        energy = 0.0
        if tda_api and hasattr(tda_api, 'states'):
            state = tda_api.states.get(edge.dst)
            if state:
                # state is a SymbolManifoldState (Pydantic model)
                if hasattr(state, 'energy') and state.energy:
                    energy = state.energy.get("total", 0.0)
                elif hasattr(state, 'topology') and hasattr(state.topology, 'energy_total'):
                    energy = state.topology.energy_total

        neighbors.append({
            "symbol": edge.dst,
            "kind": method_node.metadata.get("kind", "method"),
            "energy": energy,
            "relationship": "contains",
            "weight": edge.weight,
        })

    # Sort by energy (most important methods first)
    neighbors.sort(key=lambda x: x["energy"], reverse=True)

    return neighbors[:max_candidates]


def _get_execution_neighbors(
    executor_id: str,
    registry_adapter,
    tda_api=None,
    max_candidates: int = 5
) -> List[Dict[str, Any]]:
    """Get execution neighbors (call graph) for an executor.

    Args:
        executor_id: Executor symbol ID
        registry_adapter: Registry adapter
        tda_api: Optional TDA API for energy
        max_candidates: Max results

    Returns:
        List of neighbor dicts with symbol, kind, energy, relationship
    """
    # Get all outgoing edges except CONTAINS (structural)
    all_edges = registry_adapter.get_edges_from(executor_id)

    neighbors = []
    for edge in all_edges:
        if edge.kind == "contains":
            continue  # Skip structural edges

        target_node = registry_adapter.get_node(edge.dst)
        if not target_node:
            continue

        # Get energy from TDA if available
        energy = 0.0
        if tda_api and hasattr(tda_api, 'states'):
            state = tda_api.states.get(edge.dst)
            if state:
                # state is a SymbolManifoldState (Pydantic model)
                if hasattr(state, 'energy') and state.energy:
                    energy = state.energy.get("total", 0.0)
                elif hasattr(state, 'topology') and hasattr(state.topology, 'energy_total'):
                    energy = state.topology.energy_total

        neighbors.append({
            "symbol": edge.dst,
            "kind": target_node.metadata.get("kind", "function"),
            "energy": energy,
            "relationship": edge.kind,
            "weight": edge.weight,
        })

    # Sort by weight * energy (importance)
    neighbors.sort(key=lambda x: x["weight"] * (1 + x["energy"]), reverse=True)

    return neighbors[:max_candidates]
