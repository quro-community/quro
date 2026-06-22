"""Quro v3 MCP Service - MCP Server (compressed 3-tool surface)

@module quro_mcp.server
@intent Expose Quro navigation as 3 progressive-disclosure MCP tools.
@constraint Minimal, stateless, on-demand. service.py is unchanged.

The 17-tool legacy surface is compressed to a navigation triad (see
docs/implementation/quro-interface-consolidation.md §3):

  quro_landscape  — orientation: the map, per-center reachability, attractors
  quro_navigate   — movement: next / upstream / escape / role / path / field
  quro_lookup     — resolution: symbol/category/list/stats/cqe

Every legacy capability survives — it is re-routed, not removed. The CLI
mirrors all of them (see `quro --help`) for human/script use.
"""

import os
import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

from quro_mcp.service import QuroV3Service
from quro_mcp.type_aware_navigation import get_type_aware_neighbors


_DEFAULT_PROJECT_ROOT = os.environ.get('QURO_PROJECT_ROOT', str(Path.cwd()))

# Initialize MCP server
app = Server("quro-v3")

# Global state (initialized on first use or explicit mount)
_workspace_state = {
    "workspace_root": None,
    "cqe_service": None,
    "trajectory_planner": None,
    "initialized_at": None,
    # Per-component init status for graceful partial failure
    "cqe_ready": False,
    "tda_ready": False,
}


def _initialize_workspace(workspace_root: str) -> dict:
    """Initialize workspace: load index DB and TDA results."""
    global _workspace_state

    workspace_path = Path(workspace_root)
    status = {
        "workspace_root": workspace_root,
        "cqe_loaded": False,
        "tda_loaded": False,
        "errors": [],
    }

    try:
        _workspace_state["cqe_service"] = QuroV3Service(workspace_root=workspace_path)
        status["cqe_loaded"] = True
    except Exception as e:
        status["errors"].append(f"CQE service failed: {str(e)}")

    tda_path = workspace_path / ".quro_context" / "tda"
    if tda_path.exists():
        try:
            from tda.phase4.trajectory_planner import TrajectoryPlanner
            _workspace_state["trajectory_planner"] = TrajectoryPlanner(tda_path)
            status["tda_loaded"] = True
            status["tda_phase"] = "Phase 4 (A* planning + pickle cache)"
        except Exception as e:
            status["errors"].append(f"TDA Phase 4 load failed: {str(e)}")
    else:
        status["errors"].append(f"TDA directory not found at {tda_path}")

    _workspace_state["workspace_root"] = Path(workspace_root)
    _workspace_state["initialized_at"] = datetime.now().isoformat()
    _workspace_state["cqe_ready"] = status["cqe_loaded"]
    _workspace_state["tda_ready"] = status["tda_loaded"]

    return status


def _ensure_initialized() -> Optional[str]:
    if _workspace_state["workspace_root"] is None:
        status = _initialize_workspace(_DEFAULT_PROJECT_ROOT)
        if not status["cqe_loaded"] and not status["tda_loaded"]:
            return f"Workspace not initialized. Errors: {', '.join(status['errors'])}"
    return None


def _require_cqe() -> Optional[str]:
    err = _ensure_initialized()
    if err:
        return err
    if not _workspace_state.get("cqe_ready", False):
        return "CQE engine not loaded. Run scan + build index first."
    return None


def _require_tda() -> Optional[str]:
    err = _ensure_initialized()
    if err:
        return err
    if not _workspace_state.get("tda_ready", False):
        return "TDA data not available. Run 'quro tda pipeline all' first."
    return None


# ---------------------------------------------------------------------------
# Centers helpers (shared by quro_landscape actions)
# ---------------------------------------------------------------------------

_CENTERS_RELATIVE = Path(".quro_context") / "tda" / "phase3_5" / "semantic_centers.json"


def _get_centers_path(workspace_root: Path) -> Path:
    return workspace_root / _CENTERS_RELATIVE


def _load_centers(
    workspace_root: Path,
) -> tuple[Optional[list], Optional[dict], Optional[list[TextContent]]]:
    """Load semantic centers JSON.

    Returns (centers_list, centers_data, error_response).
    """
    centers_path = _get_centers_path(workspace_root)
    if not centers_path.exists():
        return None, None, [
            TextContent(
                type="text",
                text=json.dumps({
                    "error": "Semantic centers not found",
                    "hint": "Run Phase 3.5 first: python -m quro.tda.phase3_5",
                }),
            )
        ]
    try:
        with open(centers_path) as f:
            centers_data = json.load(f)
        return centers_data.get("centers", []), centers_data, None
    except Exception as e:
        return None, None, [
            TextContent(
                type="text",
                text=json.dumps({"error": f"Failed to load centers: {str(e)}"}),
            )
        ]


# ===========================================================================
# Tool schemas — exactly 3 tools
# ===========================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List the 3 compressed MCP tools."""
    return [
        Tool(
            name="quro_landscape",
            description=(
                "Orientation: the codebase map. Answers 'where do I start, "
                "what regions exist, what's reachable from region X, where are "
                "the attractors?'. Use this for LLM first-touch before any "
                "navigation. view=summary (default) → routing + regions + "
                "structural coupling. center_id set → reachable symbols from "
                "that center. view=attractors → attractor/repeller/saddle "
                "detection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "view": {
                        "type": "string",
                        "enum": ["summary", "attractors"],
                        "default": "summary",
                        "description": "summary=routing+region overview; attractors=energy attractor detection",
                    },
                    "center_id": {
                        "type": "string",
                        "description": "Optional: drill into one center's reachability (e.g. C0). Overrides view.",
                    },
                    "region": {
                        "type": "string",
                        "description": "For view=attractors: optional region filter (substring match).",
                    },
                    "max_symbols": {
                        "type": "integer",
                        "default": 50,
                        "description": "For center_id drill-in: reachable-symbol cap.",
                    },
                },
            },
        ),
        Tool(
            name="quro_navigate",
            description=(
                "Movement: from a symbol, decide where to go. One tool, six "
                "actions. action=next (default) → ranked next-hop candidates; "
                "upstream → top-k sources; escape → sink escape target; "
                "role → CORE_ATTRACTOR/EMITTER/SINK/TRANSIENT; path → planned "
                "trajectory to a goal; field → anisotropic field vector."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "from": {
                        "type": "string",
                        "description": "Source symbol id, e.g. 'sym::main'.",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["next", "upstream", "escape", "role", "path", "field"],
                        "default": "next",
                    },
                    "to": {
                        "type": "string",
                        "description": "Goal symbol (required for action=path).",
                    },
                    "intent": {
                        "type": "string",
                        "description": "Free-text navigation intent.",
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 5,
                        "description": "For action=upstream: number of sources.",
                    },
                    "max_depth": {
                        "type": "integer",
                        "default": 2,
                        "description": "For action=upstream: traversal depth (hard limit 2).",
                    },
                    "max_candidates": {
                        "type": "integer",
                        "default": 5,
                        "description": "For action=next: candidate cap.",
                    },
                },
                "required": ["from"],
            },
        ),
        Tool(
            name="quro_lookup",
            description=(
                "Resolution: tell me about a specific symbol/category, list "
                "them, get stats, or run a CQE semantic query. kind defaults "
                "from which of target/query is set. kind=cqe supports mode "
                "(forward/reverse/field_guided/saddle_escape) and tier "
                "(single/multi)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["symbol", "category", "list_symbols", "list_categories", "stats", "cqe"],
                        "description": "Resolution kind. If omitted, inferred from target/query.",
                    },
                    "target": {
                        "type": "string",
                        "description": "For kind=symbol/category: the name (no sym::/cat:: prefix).",
                    },
                    "query": {
                        "type": "string",
                        "description": "For kind=cqe: the start node id.",
                    },
                    "mode": {
                        "type": "string",
                        "description": "For kind=cqe: traversal mode (forward/reverse/field_guided/saddle_escape).",
                    },
                    "tier": {
                        "type": "string",
                        "enum": ["single", "multi"],
                        "default": "single",
                        "description": "For kind=cqe: single (one tau) or multi (tiered 0.3/0.1/0.05).",
                    },
                    "tau": {
                        "type": "number",
                        "default": 0.05,
                        "description": "For kind=cqe single: MI-gate threshold.",
                    },
                    "max_depth": {
                        "type": "integer",
                        "default": 3,
                        "description": "For kind=cqe: traversal depth.",
                    },
                    "use_semantic_refiner": {
                        "type": "boolean",
                        "default": True,
                    },
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "description": "For kind=list_symbols: cap.",
                    },
                },
            },
        ),
    ]


# ===========================================================================
# Tool dispatch
# ===========================================================================

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch the 3 tools to their action handlers."""
    try:
        if name == "quro_landscape":
            return _landscape(arguments)
        elif name == "quro_navigate":
            return _navigate(arguments)
        elif name == "quro_lookup":
            return _lookup(arguments)
        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": f"Unknown tool: {name}"}),
                )
            ]
    except Exception as e:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": str(e), "type": type(e).__name__}),
            )
        ]


def _err(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps({"error": msg}))]


def _ok(result: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


# ---------------------------------------------------------------------------
# quro_landscape
# ---------------------------------------------------------------------------

def _landscape(arguments: dict[str, Any]) -> list[TextContent]:
    # center_id drill-in takes precedence
    if arguments.get("center_id"):
        return _landscape_reachability(arguments)

    view = arguments.get("view", "summary")
    if view == "attractors":
        return _landscape_attractors(arguments.get("region", ""))
    return _landscape_summary()


def _landscape_summary() -> list[TextContent]:
    error = _ensure_initialized()
    if error:
        return _err(error)

    workspace_root = _workspace_state["workspace_root"]
    centers_list, centers_data, err_response = _load_centers(workspace_root)
    if err_response:
        return err_response

    structural_coupling = centers_data.get("structural_coupling", {})

    # STAGE 1: routing layer
    hub_centers = [c for c in centers_list if c.get("topology", {}).get("pattern") == "hub"]
    ranked_hubs = sorted(
        hub_centers,
        key=lambda c: (c.get("size", 0), len(c.get("topology", {}).get("entry_points", []))),
        reverse=True,
    )

    recommended = []
    if ranked_hubs:
        top_hub = ranked_hubs[0]
        entry_points = top_hub.get("topology", {}).get("entry_points", [])[:3]
        recommended.append({
            "region": top_hub["id"],
            "reason": f"{top_hub.get('topology', {}).get('pattern', 'unknown').capitalize()} center with {len(entry_points)} entry points",
            "confidence": 0.95 if len(entry_points) >= 3 else 0.8,
            "entry_points": [ep["symbol"] for ep in entry_points],
        })

    routing = {
        "instruction": "Choose a region before reading code. Start with recommended region, then explore neighbors.",
        "recommended": recommended,
    }

    # STAGE 2: region summary
    regions = []
    for center in centers_list:
        topology = center.get("topology", {})
        pattern = topology.get("pattern", "unknown")
        entry_points = topology.get("entry_points", [])[:3]
        navigation = center.get("navigation", {})
        regions.append({
            "id": center["id"],
            "role": pattern,
            "size": center.get("size", 0),
            "entry_points": [ep["symbol"] for ep in entry_points],
            "hint": navigation.get("landing_hint", f"{pattern.capitalize()} center"),
        })

    # STAGE 3: structure layer
    clusters_summary = []
    clusters_data = structural_coupling.get("clusters", [])
    for cluster in clusters_data:
        cluster_centers = [
            center["id"] for center in centers_list
            if center.get("structural_cluster_id") == cluster["id"]
        ]
        archetype = cluster.get("archetype", "loose_coupling")
        hint_map = {
            "tight_coupling": "Must change together",
            "flow_convergent": "Share downstream sinks",
            "radiation": "High fan-out influence",
            "loose_coupling": "Weakly coupled",
        }
        clusters_summary.append({
            "id": cluster["id"],
            "size": cluster.get("size", 0),
            "archetype": archetype,
            "centers": cluster_centers,
            "hint": hint_map.get(archetype, "Weakly coupled"),
        })

    couplings_compressed = []
    for coupling in structural_coupling.get("coupled_centers", [])[:20]:
        shared_sinks = coupling.get("shared_sinks", [])[:3]
        bridge_count = len(coupling.get("bridge_symbols", []))
        sink_count = len(coupling.get("shared_sinks", []))
        couplings_compressed.append({
            "center_a": coupling["center_a"],
            "center_b": coupling["center_b"],
            "score": coupling.get("coupling_score", 0.0),
            "mechanism": f"{bridge_count} bridge symbols flowing to {sink_count} shared sinks",
            "shared_sinks_sample": shared_sinks,
        })

    structure = {
        "summary": (
            f"{len(clusters_data)} {clusters_data[0].get('archetype', 'coupling') if clusters_data else 'coupling'} clusters detected, "
            f"{structural_coupling.get('cross_module_clusters', 0)} cross-module. "
            f"{len(structural_coupling.get('coupled_centers', []))} coupled center pairs."
        ),
        "clusters": clusters_summary,
        "couplings": couplings_compressed,
        "details_hint": "Use quro_landscape{center_id} or quro_navigate for deep exploration",
    }

    result = {
        "routing": routing,
        "regions": regions,
        "structure": structure,
        "total_symbols": centers_data.get("total_symbols", 0),
        "partition_coverage": centers_data.get("partition_coverage", 0.0),
    }
    return _ok(result)


def _landscape_reachability(arguments: dict[str, Any]) -> list[TextContent]:
    error = _ensure_initialized()
    if error:
        return _err(error)

    center_id = arguments["center_id"]
    max_symbols = arguments.get("max_symbols", 50)

    workspace_root = _workspace_state["workspace_root"]
    centers_list, centers_data, err_response = _load_centers(workspace_root)
    if err_response:
        return err_response

    center_by_id = {c["id"]: c for c in centers_list}
    if center_id not in center_by_id:
        return _ok({
            "error": f"Center not found: {center_id}",
            "available_centers": list(center_by_id.keys()),
        })

    target_center = center_by_id[center_id]
    entry_points = target_center.get("topology", {}).get("entry_points", [])
    if not entry_points:
        return _ok({
            "center_id": center_id,
            "reachable_symbols": [],
            "count": 0,
            "message": "No entry points defined for this center",
        })

    from tda.adapters.graph_adapter import GraphAdapter
    tda_path = workspace_root / ".quro_context" / "tda"
    graph = GraphAdapter.create(tda_path)

    center_symbols = set()
    for c in centers_list:
        for ep in c.get("topology", {}).get("entry_points", []):
            center_symbols.add(ep["symbol"])

    visited = set(center_symbols)
    reachable = []
    queue = deque()
    for ep in entry_points[:3]:
        queue.append((ep["symbol"], 0))
        visited.add(ep["symbol"])

    max_depth = 10
    while queue and len(reachable) < max_symbols:
        node, depth = queue.popleft()
        if depth > 0:
            in_different_center = True
            for c in centers_list:
                if c["id"] != center_id:
                    for ep in c.get("topology", {}).get("entry_points", []):
                        if ep["symbol"] == node:
                            in_different_center = False
                            break
            if in_different_center or len(centers_list) == 1:
                reachable.append(node)
        if depth < max_depth:
            for neighbor in graph.get_out_neighbors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

    return _ok({
        "center_id": center_id,
        "reachable_symbols": reachable[:max_symbols],
        "count": len(reachable),
        "max_symbols": max_symbols,
        "entry_points_used": [ep["symbol"] for ep in entry_points[:3]],
    })


def _landscape_attractors(region: str) -> list[TextContent]:
    error = _require_cqe()
    if error:
        return _err(error)

    from core.cqe.tda_bridge import TDABridge
    tda_bridge = TDABridge(_workspace_state["workspace_root"])
    tda_bridge._load_manifold_states()

    attractors, repellers, saddle_points = [], [], []
    for symbol_id in tda_bridge._state_cache.keys():
        if region and region not in symbol_id:
            continue
        if tda_bridge.is_attractor(symbol_id):
            attractors.append({
                "symbol": symbol_id,
                "gravity": tda_bridge.get_gravity_score(symbol_id),
                "energy": tda_bridge.get_energy_total(symbol_id),
            })
        elif tda_bridge.is_repeller(symbol_id):
            repellers.append({
                "symbol": symbol_id,
                "gravity": tda_bridge.get_gravity_score(symbol_id),
                "energy": tda_bridge.get_energy_total(symbol_id),
            })
        elif tda_bridge.is_saddle_point(symbol_id):
            saddle_points.append({
                "symbol": symbol_id,
                "gravity": tda_bridge.get_gravity_score(symbol_id),
                "energy": tda_bridge.get_energy_total(symbol_id),
            })

    return _ok({
        "attractors": sorted(attractors, key=lambda x: x["gravity"], reverse=True)[:20],
        "repellers": sorted(repellers, key=lambda x: x["gravity"])[:20],
        "saddle_points": sorted(saddle_points, key=lambda x: x["energy"], reverse=True)[:20],
        "total_attractors": len(attractors),
        "total_repellers": len(repellers),
        "total_saddle_points": len(saddle_points),
    })


# ---------------------------------------------------------------------------
# quro_navigate
# ---------------------------------------------------------------------------

def _navigate(arguments: dict[str, Any]) -> list[TextContent]:
    from_symbol = arguments["from"]
    action = arguments.get("action", "next")

    if action == "next":
        return _nav_next(arguments, from_symbol)
    elif action == "upstream":
        return _nav_upstream(arguments, from_symbol)
    elif action == "escape":
        return _nav_escape(from_symbol)
    elif action == "role":
        return _nav_role(from_symbol)
    elif action == "path":
        return _nav_path(arguments, from_symbol)
    elif action == "field":
        return _nav_field(from_symbol)
    return _err(f"Unknown action: {action}")


def _nav_next(arguments: dict[str, Any], from_symbol: str) -> list[TextContent]:
    error = _require_cqe()
    if error:
        return _err(error)
    max_candidates = arguments.get("max_candidates", 5)
    result = get_type_aware_neighbors(
        from_symbol=from_symbol,
        registry_adapter=_workspace_state["cqe_service"].registry_adapter,
        tda_api=None,
        max_candidates=max_candidates,
    )
    return _ok(result)


def _nav_upstream(arguments: dict[str, Any], symbol: str) -> list[TextContent]:
    error = _require_cqe()
    if error:
        return _err(error)
    result = _workspace_state["cqe_service"].tda_find_upstream(
        symbol=symbol,
        top_k=arguments.get("top_k", 5),
        max_depth=arguments.get("max_depth", 2),
    )
    return _ok(result)


def _nav_escape(symbol: str) -> list[TextContent]:
    error = _require_cqe()
    if error:
        return _err(error)
    return _ok(_workspace_state["cqe_service"].tda_escape_sink(symbol=symbol))


def _nav_role(symbol: str) -> list[TextContent]:
    error = _require_cqe()
    if error:
        return _err(error)
    return _ok(_workspace_state["cqe_service"].tda_classify_role(symbol=symbol))


def _nav_path(arguments: dict[str, Any], from_symbol: str) -> list[TextContent]:
    error = _require_tda()
    if error:
        return _err(error)

    planner = _workspace_state.get("trajectory_planner")
    if planner is None:
        return _ok({"error": "TDA Phase 4 not loaded", "hint": "Run Phase 2.5 and Phase 4 first"})

    goal = arguments.get("to")
    if not goal:
        return _err("action=path requires 'to' (goal symbol)")

    from tda.phase4.trajectory_planner import TrajectoryRequest, TrajectoryConstraints
    request = TrajectoryRequest(
        start=from_symbol,
        goal=goal,
        intent=arguments.get("intent"),
        constraints=TrajectoryConstraints(max_hops=arguments.get("max_depth", 10)),
    )
    plan = planner.plan_trajectory(request)
    if not plan:
        return _ok({"error": "No path found", "start": request.start, "goal": request.goal})

    result = {
        "start": plan.path[0] if plan.path else request.start,
        "goal": plan.path[-1] if plan.path else request.goal,
        "path": plan.path,
        "total_energy": plan.total_energy,
        "avg_alignment": plan.avg_alignment,
        "risk_score": plan.risk_score,
        "coherence": plan.coherence,
        "is_valid": plan.is_valid,
    }
    if plan.landing_hints:
        result["landing_hints"] = plan.landing_hints
    return _ok(result)


def _nav_field(symbol: str) -> list[TextContent]:
    error = _require_cqe()
    if error:
        return _err(error)
    return _ok(_workspace_state["cqe_service"].tda_get_field_vector(symbol))


# ---------------------------------------------------------------------------
# quro_lookup
# ---------------------------------------------------------------------------

def _lookup(arguments: dict[str, Any]) -> list[TextContent]:
    kind = arguments.get("kind")
    # Infer kind if not explicit
    if not kind:
        if arguments.get("query"):
            kind = "cqe"
        elif arguments.get("target"):
            kind = "symbol"
        else:
            return _err("kind is required (or set target/query to infer it)")

    if kind == "cqe":
        return _lookup_cqe(arguments)
    if kind == "stats":
        return _lookup_stats()

    error = _require_cqe()
    if error:
        return _err(error)
    service = _workspace_state["cqe_service"]

    if kind == "symbol":
        target = arguments.get("target")
        if not target:
            return _err("kind=symbol requires target")
        result = service.get_symbol(target)
        if result is None:
            return _ok({"error": f"Symbol not found: {target}"})
        return _ok(result)

    if kind == "category":
        target = arguments.get("target")
        if not target:
            return _err("kind=category requires target")
        result = service.get_category(target)
        if result is None:
            return _ok({"error": f"Category not found: {target}"})
        return _ok(result)

    if kind == "list_symbols":
        result = service.list_symbols(limit=arguments.get("limit", 100))
        return _ok({"symbols": result, "count": len(result)})

    if kind == "list_categories":
        result = service.list_categories()
        return _ok({"categories": result, "count": len(result)})

    return _err(f"Unknown kind: {kind}")


def _lookup_cqe(arguments: dict[str, Any]) -> list[TextContent]:
    error = _require_cqe()
    if error:
        return _err(error)

    start = arguments.get("query")
    if not start:
        return _err("kind=cqe requires query (start node)")

    service = _workspace_state["cqe_service"]
    tier = arguments.get("tier", "single")
    mode = arguments.get("mode")
    max_depth = arguments.get("max_depth", 3)
    use_refiner = arguments.get("use_semantic_refiner", True)

    if mode:
        return _ok(service.cqe_query_with_mode(
            start=start, max_depth=max_depth,
            use_semantic_refiner=use_refiner, traversal_mode=mode,
        ))
    if tier == "multi":
        return _ok(service.cqe_query_multi_tier(
            start=start, max_depth=max_depth, use_semantic_refiner=use_refiner,
        ))
    return _ok(service.cqe_query(
        start=start, tau=arguments.get("tau", 0.05),
        max_depth=max_depth, use_semantic_refiner=use_refiner,
    ))


def _lookup_stats() -> list[TextContent]:
    error = _require_cqe()
    if error:
        return _err(error)
    return _ok(_workspace_state["cqe_service"].get_stats())


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    """CLI entry point."""
    import asyncio
    asyncio.run(_main())


async def _main():
    """Internal async main."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    main()
