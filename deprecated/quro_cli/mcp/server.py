"""
MCP Server - Python implementation

Replaces node_server/mcp/server.ts

Provides 40+ tools for AI agents via Model Context Protocol.
Uses stdio transport for communication.
"""
import asyncio
import json
import sys
import os
from typing import Any, Dict, List

# MCP SDK imports (will be installed via pip)
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

from quro_cli.mcp.tools import MCPTools


# Initialize MCP server
app = Server("quro")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """
    Register all MCP tools

    Returns list of available tools with their schemas.
    """
    return [
        Tool(
            name="quro_explore",
            description=(
                "Start here — discover what Quro is and what tools are available. "
                "Returns a guided overview: tool categories, domain vocabulary, "
                "recommended workflow, and getting-started tips. No parameters needed."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="identify_symbol",
            description=(
                "Identify a symbol and return behavioral tags, source snippet, and neighbors. "
                "Auto-compacts source based on task_intent — the system decides the compression level. "
                "Example: identify_symbol(symbol='LlmGuard', task_intent='understand the lock mechanism')"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to identify"
                    },
                    "task_intent": {
                        "type": "string",
                        "description": "Optional task context for auto-compression (e.g. 'debug deadlock', 'understand the API'). System decides level."
                    },
                    "level": {
                        "type": "string",
                        "enum": ["SUMMARY", "SKELETON"],
                        "description": "[LEGACY] Compression level (default: SKELETON). Prefer task_intent."
                    },
                    "workspace_root": {
                        "type": "string",
                        "description": "Workspace root directory (optional)"
                    }
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="read_source_symbol",
            description="Read source code for a specific symbol with AST metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "File path"
                    },
                    "symbol_name": {
                        "type": "string",
                        "description": "Symbol name"
                    },
                    "line_range": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Optional line range [start, end]"
                    }
                },
                "required": ["filepath", "symbol_name"]
            }
        ),
        Tool(
            name="verify_symbol_integrity",
            description="Verify symbol exists and check integrity",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to verify"
                    }
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="distill_patch_context",
            description="Extract context for a patch (code change)",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path"
                    },
                    "line_start": {
                        "type": "integer",
                        "description": "Start line of patch"
                    },
                    "line_end": {
                        "type": "integer",
                        "description": "End line of patch"
                    }
                },
                "required": ["file_path", "line_start", "line_end"]
            }
        ),
        Tool(
            name="compact_context",
            description="Compress context using semantic analysis and deduplication",
            inputSchema={
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "Context text to compress"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens in output (default: 2000)"
                    },
                    "preserve_symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Symbols that must be preserved"
                    }
                },
                "required": ["context"]
            }
        ),
        Tool(
            name="trace_logic_path",
            description="Trace dependency path between symbols",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_symbol": {
                        "type": "string",
                        "description": "Starting symbol name"
                    },
                    "end_symbol": {
                        "type": "string",
                        "description": "Target symbol name (optional)"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum traversal depth (default: 5)"
                    }
                },
                "required": ["start_symbol"]
            }
        ),
        Tool(
            name="get_pitfall",
            description="Get known issues and pitfalls",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (e.g., async, memory, security)"
                    },
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity (e.g., critical, high, medium, low)"
                    }
                }
            }
        ),
        Tool(
            name="get_nrt_alerts",
            description="Get runtime alerts from NRT system",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity (e.g., critical, high, medium, low)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of alerts (default: 10)"
                    }
                }
            }
        ),
        Tool(
            name="cqe_query",
            description=(
                "Categorical Query Engine - semantic query over codebase categories. "
                "First-time? Call with suggest=true (no entry_token) to discover available categories. "
                "Example: cqe_query(query='concurrency pitfalls', entry_token='async'). "
                "Every response includes a 'capability' field at the end with index stats and adjustment hints. "
                "Hint IDs: 'try_lower_tau' (reduce MI pruning), 'try_different_entry_token' (seed mismatch), "
                "'call_suggest' (entry atom not found - use suggest=true to discover available tokens), "
                "'token_out_of_domain' (resolved token produced zero results - query is outside CQE's domain)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query"
                    },
                    "entry_token": {
                        "type": "string",
                        "description": "Seed category tag or symbol name (e.g., 'async', 'LlmGuard'). Not needed when suggest=true."
                    },
                    "tau": {
                        "type": "number",
                        "description": "MI-gate threshold [0,1] (default: 0.1)"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum BFS hops (default: 3)"
                    },
                    "auto_resolve": {
                        "type": "boolean",
                        "description": "Enable automatic token resolution (default: true)"
                    },
                    "use_semantic_match": {
                        "type": "boolean",
                        "description": "Use 0.6B model for semantic category matching (default: true)"
                    },
                    "suggest": {
                        "type": "boolean",
                        "description": "Discovery mode: return available categories instead of querying. No entry_token needed."
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="project_panorama",
            description="Get project overview with statistics and health metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_stats": {
                        "type": "boolean",
                        "description": "Include file/symbol statistics (default: true)"
                    },
                    "include_health": {
                        "type": "boolean",
                        "description": "Include health metrics (default: true)"
                    }
                }
            }
        ),
        Tool(
            name="query_semantic_inventory",
            description="Semantic search across workspace using LSH similarity",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Minimum similarity threshold [0.0-1.0] (default: 0.3)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_vocabulary",
            description="Get symbol vocabulary for a file with roles and intents",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path to analyze"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get_chain",
            description="Get commit chain for a symbol",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name"
                    }
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="commit_reasoning",
            description="Commit reasoning to QRA (Quantum Reasoning Archive)",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Reasoning text"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization"
                    }
                },
                "required": ["symbol", "reasoning"]
            }
        ),
        Tool(
            name="commit_chain",
            description="Commit full reasoning chain to QRA",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name"
                    },
                    "chain": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of reasoning steps"
                    }
                },
                "required": ["symbol", "chain"]
            }
        ),
        Tool(
            name="lds_audit",
            description="LDS (Logic Dependency System) audit - analyze logic dependencies",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path to audit (optional)"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to audit (optional)"
                    }
                }
            }
        ),
        Tool(
            name="patch_logic_atoms",
            description="Propose code changes with validation",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path to patch"
                    },
                    "atoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of logic atoms (DSL operations)"
                    },
                    "validation": {
                        "type": "boolean",
                        "description": "Whether to validate before applying (default: true)"
                    }
                },
                "required": ["file_path", "atoms"]
            }
        ),
        Tool(
            name="create_shadow_draft",
            description="Create draft in staging area",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name"
                    },
                    "atoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of DSL atoms"
                    },
                    "language": {
                        "type": "string",
                        "description": "Target language (python, typescript, etc.)"
                    },
                    "target_path": {
                        "type": "string",
                        "description": "Target file path"
                    },
                    "auto_eject": {
                        "type": "boolean",
                        "description": "Auto-eject after creation (default: false)"
                    }
                },
                "required": ["symbol", "atoms", "language", "target_path"]
            }
        ),
        Tool(
            name="eject_shadow_draft",
            description="Materialize draft to filesystem",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name"
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force ejection even if validation fails (default: false)"
                    }
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="get_draft_status",
            description="Poll draft status",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name"
                    }
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="approve_self_heal",
            description="Approve auto-healing proposal",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "string",
                        "description": "Proposal ID"
                    },
                    "approved": {
                        "type": "boolean",
                        "description": "Whether to approve the proposal"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional reason for approval/rejection"
                    }
                },
                "required": ["proposal_id", "approved"]
            }
        ),
        Tool(
            name="run_twin_simulation",
            description="Monte Carlo deadlock detection - run digital twin simulation",
            inputSchema={
                "type": "object",
                "properties": {
                    "atoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of DSL atoms to simulate"
                    },
                    "iterations": {
                        "type": "integer",
                        "description": "Number of Monte Carlo iterations (default: 1000)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 30)"
                    }
                },
                "required": ["atoms"]
            }
        ),
        Tool(
            name="get_twin_report",
            description="Get simulation report",
            inputSchema={
                "type": "object",
                "properties": {
                    "simulation_id": {
                        "type": "string",
                        "description": "Simulation ID"
                    }
                },
                "required": ["simulation_id"]
            }
        ),
        Tool(
            name="update_session",
            description="Update session metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Metadata to update"
                    }
                },
                "required": ["session_id", "metadata"]
            }
        ),
        Tool(
            name="get_morph_alerts",
            description="Morphism evolution alerts",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity (critical, high, medium, low)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of alerts (default: 10)"
                    }
                }
            }
        ),
        Tool(
            name="cqe_reflect",
            description="Reflection log analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_id": {
                        "type": "string",
                        "description": "Filter by query UUID"
                    },
                    "entry_atom": {
                        "type": "string",
                        "description": "Filter by atom id (e.g., 'cat::async')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum records (default: 20)"
                    },
                    "mi_summary": {
                        "type": "boolean",
                        "description": "Include per-atom payload_rate table (default: false)"
                    }
                }
            }
        ),
        Tool(
            name="cqe_diagnose",
            description=(
                "Diagnose a specific CQE query by ID. "
                "Correlates reflection log + telemetry to surface semantic voids, "
                "delivery efficiency, and per-atom decisions. "
                "Developer tool — pass query_id from a cqe_query response."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query_id": {
                        "type": "string",
                        "description": "The query_id from a cqe_query response"
                    }
                },
                "required": ["query_id"]
            }
        ),
        Tool(
            name="cqe_get_mi_stats",
            description="Get MI statistics",
            inputSchema={
                "type": "object",
                "properties": {
                    "atom_id": {
                        "type": "string",
                        "description": "Filter by atom id (e.g., 'cat::async')"
                    }
                }
            }
        ),
        # === Skeleton Graph Tools ===
        Tool(
            name="get_file_morphism",
            description="Get file morphism data (symbols, imports, exports)",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path to analyze"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="save_file_morphism",
            description="Save file morphism data to registry",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path"
                    },
                    "morphism_data": {
                        "type": "object",
                        "description": "Morphism data (symbols, imports, exports)"
                    }
                },
                "required": ["file_path", "morphism_data"]
            }
        ),
        # === Skeleton Graph Tools ===
        Tool(
            name="skeleton_query",
            description=(
                "Query module dependencies and dependents in the skeleton graph. "
                "query_type: 'dependencies', 'dependents', or 'path'. "
                "Example: skeleton_query(query_type='dependencies', module_uid='quro_lds/chain_store')"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "description": "Type of query: 'dependencies' or 'dependents'"
                    },
                    "module_uid": {
                        "type": "string",
                        "description": "Module unique identifier (file path relative to workspace)"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum traversal depth (default: 3)"
                    }
                },
                "required": ["query_type", "module_uid"]
            }
        ),
        Tool(
            name="skeleton_trace",
            description="Trace dependency path between two modules",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_uid": {
                        "type": "string",
                        "description": "Starting module UID"
                    },
                    "to_uid": {
                        "type": "string",
                        "description": "Target module UID"
                    }
                },
                "required": ["from_uid", "to_uid"]
            }
        ),
        Tool(
            name="skeleton_detect_cycles",
            description="Detect all circular dependencies in the skeleton graph",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="skeleton_export",
            description="Export skeleton graph to JSON or DOT format",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "Export format: 'json' or 'dot' (default: json)"
                    }
                }
            }
        ),
        Tool(
            name="skeleton_build",
            description="Build skeleton dependency graph from workspace scan",
            inputSchema={
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of specific files to scan (default: scan entire workspace)"
                    }
                }
            }
        ),
        Tool(
            name="quro_audit",
            description=(
                "Structural uncertainty audit — returns ClassSignatures and diagnostics. "
                "No args: workspace audit (structural mismatch, deprecated refs). "
                "file_path: single-file audit (unbound attributes, dual-write). "
                "file_path + class_name: single-class audit. "
                "Read-only: never modifies PG, CQE, or Registry. "
                "Example: quro_audit(file_path='quro_cli/scanner.py', class_name='WorkspaceScanner')"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File to audit (relative to workspace root). Omit for workspace-level audit."
                    },
                    "class_name": {
                        "type": "string",
                        "description": "Class to audit (requires file_path). Returns ClassSignature + unbound attrs."
                    },
                    "workspace_root": {
                        "type": "string",
                        "description": "Override workspace root (optional)"
                    }
                }
            }
        ),
        Tool(
            name="call_graph",
            description=(
                "Query the call graph for a symbol using existing CALLS morphism edges. "
                "Returns adjacency lists (calls, called_by), all edges in the traversal, "
                "and graph freshness timestamp. "
                "BFS traversal respects depth parameter and excludes deprecated symbols. "
                "Example: call_graph(symbol='LlmGuard', depth=2)"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to start traversal from"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum BFS depth (default: 2, max: 10)"
                    }
                },
                "required": ["symbol"]
            }
        ),
    ]


# Global tools instance (initialized in main)
tools_instance = None


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Route tool calls to handlers

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        List of text content responses
    """
    global tools_instance

    if tools_instance is None:
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "error": "Tools not initialized"
            }, indent=2)
        )]

    if name == "quro_explore":
        result = await tools_instance.quro_explore(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    if name == "identify_symbol":
        result = await tools_instance.identify_symbol(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "read_source_symbol":
        result = await tools_instance.read_source_symbol(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "verify_symbol_integrity":
        result = await tools_instance.verify_symbol_integrity(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "distill_patch_context":
        result = await tools_instance.distill_patch_context(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "compact_context":
        result = await tools_instance.compact_context(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "trace_logic_path":
        result = await tools_instance.trace_logic_path(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_pitfall":
        result = await tools_instance.get_pitfall(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_nrt_alerts":
        result = await tools_instance.get_nrt_alerts(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "cqe_query":
        result = await tools_instance.cqe_query(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "project_panorama":
        result = await tools_instance.project_panorama(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "query_semantic_inventory":
        result = await tools_instance.query_semantic_inventory(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_vocabulary":
        result = await tools_instance.get_vocabulary(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_chain":
        result = await tools_instance.get_chain(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "commit_reasoning":
        result = await tools_instance.commit_reasoning(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "commit_chain":
        result = await tools_instance.commit_chain(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "lds_audit":
        result = await tools_instance.lds_audit(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "patch_logic_atoms":
        result = await tools_instance.patch_logic_atoms(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "create_shadow_draft":
        result = await tools_instance.create_shadow_draft(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "eject_shadow_draft":
        result = await tools_instance.eject_shadow_draft(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_draft_status":
        result = await tools_instance.get_draft_status(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "approve_self_heal":
        result = await tools_instance.approve_self_heal(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "run_twin_simulation":
        result = await tools_instance.run_twin_simulation(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_twin_report":
        result = await tools_instance.get_twin_report(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "update_session":
        result = await tools_instance.update_session(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_morph_alerts":
        result = await tools_instance.get_morph_alerts(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "cqe_reflect":
        result = await tools_instance.cqe_reflect(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "cqe_diagnose":
        result = await tools_instance.cqe_diagnose(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "cqe_get_mi_stats":
        result = await tools_instance.cqe_get_mi_stats(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_file_morphism":
        result = await tools_instance.get_file_morphism(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "save_file_morphism":
        result = await tools_instance.save_file_morphism(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "skeleton_query":
        result = await tools_instance.skeleton_query(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "skeleton_trace":
        result = await tools_instance.skeleton_trace(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "skeleton_detect_cycles":
        result = await tools_instance.skeleton_detect_cycles()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "skeleton_export":
        result = await tools_instance.skeleton_export(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "skeleton_build":
        result = await tools_instance.skeleton_build(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "quro_audit":
        result = await tools_instance.quro_audit(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "call_graph":
        result = await tools_instance.call_graph(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """
    Entry point for MCP server

    Starts stdio server and runs until interrupted.
    """
    global tools_instance

    # Get configuration from environment
    workspace_root = os.getenv("QURO_PROJECT_ROOT", os.getcwd())
    db_url = os.getenv("QURO_DB_URL")  # Optional - only needed for tools that use registry
    tsconfig_path = os.getenv("QURO_TSCONFIG_PATH")

    # Initialize tools (db_url is optional)
    # All tool modules are lazily initialized on first call — no setup() needed.
    # This avoids the 3-5 second PostgreSQL connection delay at MCP server startup.
    tools_instance = MCPTools(
        workspace_root=workspace_root,
        db_url=db_url,
        tsconfig_path=tsconfig_path
    )

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    finally:
        if tools_instance:
            await tools_instance.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
