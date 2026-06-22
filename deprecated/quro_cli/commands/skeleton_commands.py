"""
Skeleton Commands - CLI plugin for Skeleton Graph (module/symbol dependency DAG)

@module quro_cli.commands.skeleton_commands
@intent Provide CLI commands for building, querying, and exporting the
        skeleton dependency graph.

Commands:
  - skeleton-build: Build dependency graph from workspace scan
  - skeleton-query: Query dependencies or dependents of a module
  - skeleton-trace: Trace path between two modules
  - skeleton-cycles: Detect and list circular dependencies
  - skeleton-export: Export graph to JSON or DOT format
"""

import click
import asyncio
import json
from pathlib import Path


METADATA = {
    'description': 'Skeleton Graph - Module/symbol dependency DAG builder and query engine',
    'commands': {
        'skeleton-build': {
            'description': 'Build dependency graph from workspace scan',
            'usage': 'quro skeleton-build [--workspace .]',
            'implementation': 'quro_cli/commands/skeleton_commands.py:skeleton_build'
        },
        'skeleton-query': {
            'description': 'Query dependencies or dependents of a module',
            'usage': 'quro skeleton-query --type dependencies --module src/a.py [--depth 2]',
            'implementation': 'quro_cli/commands/skeleton_commands.py:skeleton_query'
        },
        'skeleton-trace': {
            'description': 'Trace dependency path between two modules',
            'usage': 'quro skeleton-trace --from src/a.py --to src/d.py',
            'implementation': 'quro_cli/commands/skeleton_commands.py:skeleton_trace'
        },
        'skeleton-cycles': {
            'description': 'Detect and list circular dependencies',
            'usage': 'quro skeleton-cycles',
            'implementation': 'quro_cli/commands/skeleton_commands.py:skeleton_cycles'
        },
        'skeleton-export': {
            'description': 'Export graph to JSON or DOT format',
            'usage': 'quro skeleton-export [--format json] [--output graph.json]',
            'implementation': 'quro_cli/commands/skeleton_commands.py:skeleton_export'
        },
    }
}


def register(cli: click.Group):
    """Register skeleton commands with CLI."""
    cli.add_command(skeleton_build)
    cli.add_command(skeleton_query)
    cli.add_command(skeleton_trace)
    cli.add_command(skeleton_cycles)
    cli.add_command(skeleton_export)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@click.command('skeleton-build')
@click.option('--workspace', type=click.Path(exists=True), default='.',
              help='Workspace root directory')
def skeleton_build(workspace: str):
    """Build dependency graph from workspace scan."""
    from quro_lds.skeleton_graph import GraphBuilder, SkeletonStore

    ws = Path(workspace)
    click.echo(f"Building skeleton graph: {ws}")

    builder = GraphBuilder(ws)
    store = SkeletonStore(ws)

    graph = asyncio.run(builder.build_module_graph())

    asyncio.run(store.save_graph(graph))

    click.echo(f"  Nodes:    {len(graph.nodes)}")
    click.echo(f"  Edges:    {len(graph.edges)}")
    click.echo(f"  Cycles:   {len(graph.cycles)}")
    click.echo(f"  Checksum: {graph.checksum}")
    click.echo(f"  Built at: {graph.built_at.isoformat()}")

    if graph.cycles:
        click.echo(f"\n  Cycles detected:")
        for c in graph.cycles:
            path_str = " -> ".join(c.cycle_path)
            click.echo(f"    [{c.risk_level}] {path_str}")

    click.echo(f"\n  Saved to: .quro_context/skeleton_graph.jsonl")


@click.command('skeleton-query')
@click.option('--type', 'query_type', type=click.Choice(['dependencies', 'dependents']),
              required=True, help='Query type: dependencies or dependents')
@click.option('--module', 'module_uid', required=True,
              help='Module UID (file path relative to workspace)')
@click.option('--depth', default=1, type=int,
              help='Traversal depth (default: 1)')
@click.option('--workspace', type=click.Path(exists=True), default='.',
              help='Workspace root directory')
def skeleton_query(query_type: str, module_uid: str, depth: int, workspace: str):
    """Query dependencies or dependents of a module."""
    from quro_lds.skeleton_graph import QueryEngine, SkeletonStore

    ws = Path(workspace)
    store = SkeletonStore(ws)

    graph = asyncio.run(store.load_graph())
    if graph is None:
        click.echo("Error: Graph not built. Run 'quro skeleton-build' first.", err=True)
        raise SystemExit(1)

    engine = QueryEngine(graph)

    if query_type == "dependencies":
        result = engine.get_dependencies(module_uid, depth)
        label = "Dependencies"
    else:
        result = engine.get_dependents(module_uid, depth)
        label = "Dependents"

    click.echo(f"{label} of {module_uid} (depth={result.depth}):")
    if not result.related_modules:
        click.echo("  (none)")
    else:
        for node in result.related_modules:
            tags = ""
            if node.behavioral_tags:
                tags = f" [{', '.join(node.behavioral_tags)}]"
            click.echo(f"  {node.uid}{tags}")


@click.command('skeleton-trace')
@click.option('--from', 'from_uid', required=True,
              help='Starting module UID')
@click.option('--to', 'to_uid', required=True,
              help='Target module UID')
@click.option('--workspace', type=click.Path(exists=True), default='.',
              help='Workspace root directory')
def skeleton_trace(from_uid: str, to_uid: str, workspace: str):
    """Trace dependency path between two modules."""
    from quro_lds.skeleton_graph import QueryEngine, SkeletonStore

    ws = Path(workspace)
    store = SkeletonStore(ws)

    graph = asyncio.run(store.load_graph())
    if graph is None:
        click.echo("Error: Graph not built. Run 'quro skeleton-build' first.", err=True)
        raise SystemExit(1)

    engine = QueryEngine(graph)
    result = engine.trace_path(from_uid, to_uid)

    if not result.found:
        click.echo(f"No path found: {from_uid} -> {to_uid}")
        raise SystemExit(1)

    click.echo(f"Path ({result.total_depth} hops):")
    current = from_uid
    for edge in result.path:
        click.echo(f"  {edge.from_uid} --[{edge.edge_type}]--> {edge.to_uid}")


@click.command('skeleton-cycles')
@click.option('--workspace', type=click.Path(exists=True), default='.',
              help='Workspace root directory')
@click.option('--module', 'filter_module', default=None,
              help='Filter cycles involving this module')
def skeleton_cycles(workspace: str, filter_module: str):
    """Detect and list circular dependencies."""
    from quro_lds.skeleton_graph import QueryEngine, SkeletonStore

    ws = Path(workspace)
    store = SkeletonStore(ws)

    graph = asyncio.run(store.load_graph())
    if graph is None:
        click.echo("Error: Graph not built. Run 'quro skeleton-build' first.", err=True)
        raise SystemExit(1)

    cycles = graph.cycles
    if filter_module:
        engine = QueryEngine(graph)
        cycles = engine.get_cycles_involving(filter_module)

    if not cycles:
        click.echo("No circular dependencies detected.")
        return

    click.echo(f"Circular dependencies ({len(cycles)} found):")
    for c in cycles:
        path_str = " -> ".join(c.cycle_path)
        click.echo(f"  [{c.risk_level}] {path_str}")


@click.command('skeleton-export')
@click.option('--format', 'fmt', type=click.Choice(['json', 'dot']), default='json',
              help='Export format (default: json)')
@click.option('--output', 'output_path', default=None,
              help='Output file path (default: stdout)')
@click.option('--workspace', type=click.Path(exists=True), default='.',
              help='Workspace root directory')
def skeleton_export(fmt: str, output_path: str, workspace: str):
    """Export graph to JSON or DOT format."""
    from quro_lds.skeleton_graph import SkeletonStore

    ws = Path(workspace)
    store = SkeletonStore(ws)

    graph = asyncio.run(store.load_graph())
    if graph is None:
        click.echo("Error: Graph not built. Run 'quro skeleton-build' first.", err=True)
        raise SystemExit(1)

    if fmt == "json":
        data = {
            "nodes": [
                {
                    "uid": n.uid,
                    "file_path": n.file_path,
                    "language": n.language,
                    "exports": list(n.exports),
                    "imports": list(n.imports),
                }
                for n in graph.nodes
            ],
            "edges": [
                {
                    "from": e.from_uid,
                    "to": e.to_uid,
                    "type": e.edge_type,
                    "symbols": list(e.symbols_imported),
                }
                for e in graph.edges
            ],
            "cycles": [
                {
                    "path": list(c.cycle_path),
                    "risk": c.risk_level,
                }
                for c in graph.cycles
            ],
            "stats": {
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "cycles": len(graph.cycles),
                "checksum": graph.checksum,
                "built_at": graph.built_at.isoformat(),
            },
        }
        content = json.dumps(data, indent=2)

    elif fmt == "dot":
        lines = ["digraph skeleton_graph {"]
        for n in graph.nodes:
            lines.append(f'  "{n.uid}";')
        for e in graph.edges:
            label = ""
            if e.symbols_imported:
                sym_list = ", ".join(e.symbols_imported)
                label = f' [label="{sym_list}"]'
            lines.append(f'  "{e.from_uid}" -> "{e.to_uid}"{label};')
        lines.append("}")
        content = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(content)
        click.echo(f"Exported to: {output_path}")
    else:
        click.echo(content)
