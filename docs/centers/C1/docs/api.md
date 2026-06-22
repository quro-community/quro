# C1 API Surface — Leaf-Dominated Fanout Utility Layer

## 1. GraphInterface (ABC) — `tda/interfaces/graph.py`

Abstract base class for all TDA graph data sources.

### Methods

| Signature | Description | Returns |
|-----------|-------------|---------|
| `get_out_neighbors(node: str) -> List[str]` | Get outgoing neighbors | List of node IDs |
| `get_in_neighbors(node: str) -> List[str]` | Get incoming neighbors | List of node IDs |
| `get_all_nodes() -> List[str]` | Get all nodes in graph | List of node IDs |
| `has_node(node: str) -> bool` | Check node existence | True/False |
| `num_nodes() -> int` | Total node count | Integer |
| `num_edges() -> int` | Total edge count | Integer |
| `get_edge_weight(src: str, dst: str) -> Optional[float]` | Get edge weight | Float or None |
| `out_degree(node: str) -> int` | Outgoing edge count | Integer |
| `in_degree(node: str) -> int` | Incoming edge count | Integer |
| `degree(node: str) -> int` | Total degree | Integer |
| `bfs(start, max_depth=10, direction="out") -> List[Tuple[str, int]]` | BFS traversal | (node, depth) pairs |
| `find_path(src, dst, max_depth=10, direction="out") -> Optional[List[str]]` | Path finding | List of nodes or None |
| `subgraph(nodes: Set[str]) -> SubgraphView` | Subgraph view | SubgraphView instance |

## 2. GraphAdapter (Protocol) — `adapters/graph/protocol.py`

Protocol for CQE graph data access.

### Methods

| Signature | Description | Returns |
|-----------|-------------|---------|
| `get_node(node_id: str) -> GraphNode | None` | Get node by ID | GraphNode or None |
| `neighbors(node_id: str) -> Iterable[Tuple[str, float]]` | Get neighbors for CQE traversal | (neighbor, weight) iterable |
| `edges(node_id: str) -> Iterable[GraphEdge]` | Get outgoing edges | GraphEdge iterable |
| `out_degree(node_id: str) -> int` | Out-degree | Integer |
| `tags(node_id: str) -> Tuple[str, ...]` | Node tags | Tuple of strings |
| `reverse_neighbors(node_id: str) -> Iterable[Tuple[str, float]]` | Incoming neighbors | (source, weight) iterable |
| `in_degree(node_id: str) -> int` | In-degree | Integer |

## 3. GraphAdapter Factory — `tda/adapters/graph_adapter.py`

### Static Methods

| Signature | Description | Returns |
|-----------|-------------|---------|
| `create(field_data_path: Path, preferred_source: str = None) -> GraphInterface` | Auto-detect best source | GraphInterface implementation |
| `create_with_fallback(field_data_path: Path, fallback_to_jsonl: bool = True) -> GraphInterface` | Create with explicit fallback | GraphInterface implementation |
| `list_available_sources(field_data_path: Path) -> List[str]` | List available sources | List of source descriptions |

Source priority: `cache` > `field_cache` > `manifold` > `sqlite` > `jsonl`

## 4. SQLiteGraphAdapter — `adapters/graph/sqlite.py`

### Constructor
`SQLiteGraphAdapter(db_path: Path | str)`

### Methods
| Signature | Description | Returns |
|-----------|-------------|---------|
| `neighbors(node: str) -> Iterable[Tuple[str, float]]` | Get neighbors | (neighbor, weight) iterable |
| `get_stats() -> Dict[str, int]` | Graph statistics | {node_count, edge_count} |

## 5. DuckDBGraphAdapter — `adapters/graph/duckdb.py`

Context manager based adapter.

### Constructor
`DuckDBGraphAdapter(db_path: Path)`

### Methods

| Signature | Description | Returns |
|-----------|-------------|---------|
| `__enter__()` | Open connection | self |
| `__exit__(*args)` | Close connection | None |
| `get_node(node_id) -> Optional[GraphNode]` | Get node | GraphNode or None |
| `neighbors(node_id) -> Iterable[Tuple[str, float]]` | Get neighbors | (neighbor, weight) iterable |
| `edges(node_id) -> Iterable[GraphEdge]` | Get edges | GraphEdge iterable |
| `out_degree(node_id) -> int` | Out-degree | Integer |
| `tags(node_id) -> Tuple[str, ...]` | Tags | Tuple of strings |
| `reverse_neighbors(node_id) -> Iterable[Tuple[str, float]]` | Incoming neighbors | (source, weight) iterable |
| `in_degree(node_id) -> int` | In-degree | Integer |

## 6. TDA File-Based Adapters — `tda/adapters/file_graph.py`

### FileGraphAdapter
`FileGraphAdapter(cache_path: Path)` — Reads `adjacency_cache.pkl`

### FieldDataGraphAdapter
`FieldDataGraphAdapter(cache_path: Path)` — Reads `field_data_cache.pkl`

### MemoryGraphAdapter
`MemoryGraphAdapter()` — In-memory graph for testing
- `add_edge(src, dst, weight=1.0)` — Add edge
- `add_node(node)` — Add node

### StreamingGraphAdapter
`StreamingGraphAdapter(events_path: Path)` — Parses `graph_events.jsonl`

All implement `GraphInterface` (see Section 1).

## 7. IO SQLite Adapters — `io/adapters/sqlite.py`

### SQLiteGraphAdapter (IO-level)
`SQLiteGraphAdapter(db_path: Path | str)`
- `neighbors(node) -> Iterable[Tuple[str, float]]` — Get neighbors
- `get_stats() -> Dict[str, int]` — {node_count, edge_count}

### SQLiteIndexLoader
`SQLiteIndexLoader(db_path: Path)` — Loads index data from SQLite

## 8. SQLiteTDAGraphAdapter — `io/adapters/sqlite_tda.py`

TDA-specific SQLite adapter.

## 9. SQLiteRegistryAdapter — `index_builder/adapters/sqlite.py`

`SQLiteRegistryAdapter(db_path: Path)` — Persistent storage adapter.

### Methods

| Signature | Description | Returns |
|-----------|-------------|---------|
| `save_node(node: GraphNode)` | Save node | None |
| `save_edge(edge: GraphEdge)` | Save edge | None |
| `get_node(node_id: str) -> Optional[GraphNode]` | Get node | GraphNode or None |
| `get_edges_from(node_id: str) -> List[GraphEdge]` | Get outgoing edges | List of GraphEdge |
| `node_exists(node_id: str) -> bool` | Check existence | Boolean |
| `get_all_nodes() -> List[GraphNode]` | All nodes | List of GraphNode |
| `get_all_edges() -> List[GraphEdge]` | All edges | List of GraphEdge |
| `clear()` | Clear all data | None |
| `find_symbol_aliases(symbol_name: str) -> List[Dict]` | Find aliases | List of alias metadata |

## 10. CQEGraphAdapter — `quro_mcp/service.py`

Bridge between RegistryAdapter and CQE GraphProtocol.

### Constructor
`CQEGraphAdapter(registry, mi_adjuster=None)`

### Methods

| Signature | Description | Returns |
|-----------|-------------|---------|
| `neighbors(node: str)` | MI-adjusted neighbors with Top-K pruning | Yields (dst, weight) |
| `edges(node: str)` | Raw edges | GraphEdge iterable |
| `out_degree(node: str) -> int` | Out-degree | Integer |

## 11. ManifoldAdapter (Protocol) — `adapters/manifold/protocol.py`

### Methods

| Signature | Description | Returns |
|-----------|-------------|---------|
| `setup()` | Initialize adapter | None |
| `upsert_node(request: NodeInsertRequest) -> ManifoldNode` | Insert or update node | ManifoldNode |
| `get_node(symbol_uid: str) -> Optional[ManifoldNode]` | Get node | ManifoldNode or None |
| `get_all_nodes() -> List[ManifoldNode]` | All nodes | List of ManifoldNode |
| `delete_node(symbol_uid: str) -> bool` | Delete node | True/False |

## 12. Visualization Components

### VisualizationService — `service/visualization_service.py`

| Signature | Description | Returns |
|-----------|-------------|---------|
| `initialize(workspace_root: Path)` | Init service | None |
| `generate_all()` | Generate all visualizations | Dict with paths |
| `generate_energy_heatmap() -> Path` | Energy heatmap | File path |
| `generate_gradient_field() -> Path` | Gradient field | File path |
| `generate_attractor_basins() -> Path` | Attractor basins | File path |
| `generate_dashboard() -> Path` | Dashboard | File path |
| `generate_html_report() -> Path` | HTML report | File path |
| `list_visualizations() -> List[str]` | List generated files | Filename list |

### FieldPlotter — `tda/visualization/__init__.py`

| Signature | Description | Returns |
|-----------|-------------|---------|
| `plot_energy_heatmap(positions, energies, title, output_filename) -> Path` | Energy heatmap | File path |
| `plot_gradient_field(positions, energies, directions, magnitudes, title, output_filename) -> Path` | Gradient field | File path |
| `plot_attractor_basins(positions, energies, roles, title, output_filename) -> Path` | Attractor basins | File path |
| `plot_trajectory(positions, energies, path, trajectory_energies, title, output_filename) -> Path` | Trajectory | File path |
| `plot_coherence_analysis(trajectory_path, direction_vectors, coherence_scores, title, output_filename) -> Path` | Coherence | File path |
| `create_summary_dashboard(positions, energies, roles, directions, magnitudes, output_filename) -> Path` | Dashboard | File path |

### VisualizeCommand — `cli/commands/visualize.py`

CLI command with subcommands: `all`, `energy`, `gradient`, `basins`, `dashboard`, `report`

## 13. Data Types

| Type | Module | Fields |
|------|--------|--------|
| `GraphNode` | `adapters/graph/types.py` | `id: str`, `type: str`, `tags: Tuple[str, ...]` |
| `GraphEdge` | `adapters/graph/types.py` | `src: str`, `dst: str`, `kind: str`, `weight: float` |
| `GraphMetadata` | `tda/interfaces/graph.py` | `num_nodes: int`, `num_edges: int`, `created_at: str`, `source: str`, `phase: str`, `version: str` |
| `ManifoldNode` | `adapters/manifold/types.py` | Symbol manifold state |
| `NodeInsertRequest` | `adapters/manifold/types.py` | Upsert request payload |
| `MIGateComponents` | `tda/phase3/adaptive_mi_gate.py` | `weights`, `mean`, `std_dev`, `k_factor`, `threshold`, `is_uniform` |
