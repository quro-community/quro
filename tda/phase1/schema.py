"""
Pydantic models for Phase-1 event schema.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Phase-1 event types."""
    NODE_VISIT = "NODE_VISIT"
    EDGE_TRAVERSE = "EDGE_TRAVERSE"
    PATH_COMPLETE = "PATH_COMPLETE"


class EdgeType(str, Enum):
    """Graph edge types."""
    CALL = "CALL"
    IMPORT = "IMPORT"
    CATEGORY = "CATEGORY"
    LOCK = "LOCK"
    INHERIT = "INHERIT"
    ASYNC_CALL = "ASYNC_CALL"
    AWAIT = "AWAIT"
    # Lowercase variants (for compatibility)
    calls = "calls"
    imports = "imports"
    category = "category"
    inherits = "inherits"


class Direction(str, Enum):
    """Edge direction."""
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class NodeInfo(BaseModel):
    """Node metadata."""
    id: str = Field(..., description="Canonical symbol ID")
    kind: str = Field(..., description="Symbol type (function/class/method)")
    file_path: str = Field(..., description="Source file path")
    line_number: int = Field(..., description="Line number in source")
    signature: Optional[str] = Field(None, description="Function/method signature")


class VisitContext(BaseModel):
    """Context for node visit event."""
    depth: int = Field(..., description="BFS depth when visited")
    predecessor: Optional[str] = Field(None, description="Node ID that led to this visit")
    via_edge_type: Optional[str] = Field(None, description="Edge type traversed to reach here")


class NodeVisitEvent(BaseModel):
    """Node visit event."""
    event_type: Literal[EventType.NODE_VISIT] = EventType.NODE_VISIT
    event_id: str = Field(..., description="Unique event ID")
    timestamp: int = Field(..., description="Unix epoch (microseconds)")
    query_id: str = Field(..., description="Links events from same query")
    node: NodeInfo
    visit_context: VisitContext


class EdgeInfo(BaseModel):
    """Edge metadata."""
    src: str = Field(..., description="Source node ID")
    dst: str = Field(..., description="Destination node ID")
    edge_type: str = Field(..., description="Edge type (any string)")
    weight: float = Field(..., description="Edge weight (MI or semantic score)")
    direction: Direction = Field(..., description="Edge direction")


class TraverseContext(BaseModel):
    """Context for edge traverse event."""
    depth: int = Field(..., description="BFS depth when traversed")
    tau_threshold: float = Field(..., description="MI-gate threshold for this query")
    passed_gate: bool = Field(..., description="Whether edge passed MI gate")


class EdgeTraverseEvent(BaseModel):
    """Edge traversal event."""
    event_type: Literal[EventType.EDGE_TRAVERSE] = EventType.EDGE_TRAVERSE
    event_id: str = Field(..., description="Unique event ID")
    timestamp: int = Field(..., description="Unix epoch (microseconds)")
    query_id: str = Field(..., description="Links events from same query")
    edge: EdgeInfo
    traverse_context: TraverseContext


class PathEdge(BaseModel):
    """Edge in a path."""
    type: str
    weight: float


class PathInfo(BaseModel):
    """Path metadata."""
    nodes: List[str] = Field(..., description="Ordered list of node IDs in path")
    edges: List[PathEdge] = Field(..., description="Ordered list of edges")
    total_length: int = Field(..., description="Number of edges in path")


class PathContext(BaseModel):
    """Context for path complete event."""
    entry_point: str = Field(..., description="Query start node")
    target: str = Field(..., description="Query target node")
    is_shortest: bool = Field(..., description="Whether this is a shortest path")


class PathCompleteEvent(BaseModel):
    """Path complete event."""
    event_type: Literal[EventType.PATH_COMPLETE] = EventType.PATH_COMPLETE
    event_id: str = Field(..., description="Unique event ID")
    timestamp: int = Field(..., description="Unix epoch (microseconds)")
    query_id: str = Field(..., description="Links events from same query")
    path: PathInfo
    path_context: PathContext


class QueryParams(BaseModel):
    """Query parameters."""
    start: str = Field(..., description="Entry symbol for traversal")
    target: Optional[str] = Field(None, description="Target symbol (None for full traversal)")
    tau: float = Field(..., description="MI-gate threshold")
    max_depth: int = Field(..., description="BFS depth limit")
    mode: str = Field(..., description="Query mode (semantic/execution/offline_batch)")


class ExecutionStats(BaseModel):
    """Query execution statistics."""
    duration_ms: Optional[float] = Field(None, description="Query duration in milliseconds")
    nodes_visited: Optional[int] = Field(None, description="Number of nodes visited")
    edges_traversed: Optional[int] = Field(None, description="Number of edges traversed")


class QueryMetadata(BaseModel):
    """Query metadata record."""
    record_type: Literal["QUERY_METADATA"] = "QUERY_METADATA"
    query_id: str = Field(..., description="Unique query ID")
    timestamp: int = Field(..., description="Unix epoch (microseconds)")
    query_params: QueryParams
    execution_stats: ExecutionStats = Field(default_factory=ExecutionStats)
