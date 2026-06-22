"""
CQE Daemon CLI Commands

@module quro_cli.commands.cqe_daemon_commands
@intent Provide CLI interface for CQE daemon management
"""
import asyncio
import sys
from pathlib import Path

import click

from quro_sovereign.cqe_daemon import CQEDaemon


@click.group(name='cqe-daemon')
def cqe_daemon_group():
    """CQE Daemon management commands"""
    pass


@cqe_daemon_group.command(name='start')
@click.option(
    '--index-path',
    type=click.Path(),
    default='.quro_context/cqe_index.db',
    help='Path to CQE index database (created on first start if missing)'
)
@click.option(
    '--socket-path',
    default='/tmp/quro_cqe.sock',
    help='Unix socket path'
)
@click.option(
    '--pid-file',
    default='/tmp/quro_cqe.pid',
    help='PID file path'
)
@click.option(
    '--advanced',
    is_flag=True,
    help='Use advanced daemon with zero-copy and git watcher'
)
@click.option(
    '--no-git-watcher',
    is_flag=True,
    help='Disable git watcher (advanced mode only)'
)
@click.option(
    '--no-zero-copy',
    is_flag=True,
    help='Disable zero-copy transfer (advanced mode only)'
)
@click.option(
    '--no-mi',
    is_flag=True,
    help='Disable MI estimator (use flat 0.8 fallback for speed)'
)
def start_daemon(index_path, socket_path, pid_file, advanced, no_git_watcher, no_zero_copy, no_mi):
    """Start CQE daemon"""
    if advanced:
        from quro_sovereign.cqe_daemon_advanced import CQEDaemonAdvanced

        daemon = CQEDaemonAdvanced(
            index_path=Path(index_path),
            project_root=Path('.'),
            socket_path=socket_path,
            pid_file=pid_file,
            enable_git_watcher=not no_git_watcher,
            enable_zero_copy=not no_zero_copy,
            enable_mi=not no_mi
        )
    else:
        daemon = CQEDaemon(
            index_path=Path(index_path),
            socket_path=socket_path,
            pid_file=pid_file,
            enable_mi=not no_mi
        )

    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        print("\n🛑 Daemon stopped by user")
        sys.exit(0)


@cqe_daemon_group.command(name='stop')
@click.option(
    '--socket-path',
    default='/tmp/quro_cqe.sock',
    help='Unix socket path'
)
@click.option(
    '--pid-file',
    default='/tmp/quro_cqe.pid',
    help='PID file path'
)
def stop_daemon(socket_path, pid_file):
    """Stop CQE daemon"""
    daemon = CQEDaemon(
        index_path=Path('.quro_context/cqe_index.db'),  # Not used for stop
        socket_path=socket_path,
        pid_file=pid_file
    )

    asyncio.run(daemon.stop())


@cqe_daemon_group.command(name='status')
@click.option(
    '--socket-path',
    default='/tmp/quro_cqe.sock',
    help='Unix socket path'
)
@click.option(
    '--pid-file',
    default='/tmp/quro_cqe.pid',
    help='PID file path'
)
def status_daemon(socket_path, pid_file):
    """Check CQE daemon status"""
    daemon = CQEDaemon(
        index_path=Path('.quro_context/cqe_index.db'),  # Not used for status
        socket_path=socket_path,
        pid_file=pid_file
    )

    asyncio.run(daemon.status())


@cqe_daemon_group.command(name='health')
@click.option(
    '--socket-path',
    default='/tmp/quro_cqe.sock',
    help='Unix socket path'
)
def health_daemon(socket_path):
    """Check CQE daemon health and build diagnostics."""
    import json

    async def _health():
        reader, writer = await asyncio.open_unix_connection(socket_path)

        request = {"command": "health"}
        request_data = json.dumps(request).encode()
        writer.write(request_data)
        await writer.drain()

        length_header = await reader.readexactly(4)
        response_length = int.from_bytes(length_header, byteorder='big')
        response_data = await reader.readexactly(response_length)
        response = json.loads(response_data.decode())

        writer.close()
        await writer.wait_closed()
        return response

    try:
        result = asyncio.run(_health())
        status = result.get("status", "unknown")
        icon = "✅" if status == "healthy" else ("⚠️" if status == "degraded" else "❌")
        print(f"{icon} CQE Daemon: {status}")

        if "index" in result:
            idx = result["index"]
            print(f"\n📊 Index:")
            print(f"  Atoms: {idx.get('atoms', 0):,}")
            print(f"  Morphisms: {idx.get('morphisms', 0):,}")
            print(f"  Payloads: {idx.get('payloads', 0):,}")
            print(f"  Size: {idx.get('size_mb', 0):.2f} MB")

        if "manifest" in result:
            m = result["manifest"]
            print(f"\n📋 Manifest:")
            print(f"  Branch: {m.get('branch')}")
            print(f"  Commit: {m.get('commit')}")
            print(f"  Symbols: {m.get('symbol_count', 0):,}")

        if "build" in result:
            b = result["build"]
            print(f"\n🔨 Last Build:")
            print(f"  Version: {b.get('version')}")
            print(f"  Build time: {b.get('build_time_sec', 0):.1f}s")

        if "invariants" in result:
            inv = result["invariants"]
            icon = "✅" if inv.get("passed") else "❌"
            print(f"\n🛡️  Invariants: {icon}")
            if not inv.get("passed"):
                print(f"  Structural: {inv.get('structural_violations', 0)}")
                print(f"  Alias: {inv.get('alias_violations', 0)}")
                print(f"  Path decay: {inv.get('path_decay_violations', 0)}")

        if "detox" in result:
            d = result["detox"]
            icon = "✅" if d.get("is_healthy") else "⚠️"
            print(f"\n🧹 Detox: {icon}")
            print(f"  Entropy: {d.get('entropy_score', 0):.2f}")
            print(f"  God nodes: {d.get('god_nodes', 0)}")
            print(f"  Hub ratio: {d.get('hub_ratio', 0):.4f}")

        if "mi" in result:
            mi = result["mi"]
            print(f"\n🧠 MI Adjustment:")
            print(f"  Events: {mi.get('events_loaded', 0)}")
            print(f"  Atoms with MI: {mi.get('atoms_with_mi', 0)}")
            print(f"  Morphisms adjusted: {mi.get('morphisms_adjusted', 0)}")

        if "alias_merge" in result:
            am = result["alias_merge"]
            print(f"\n🔗 Alias Merge:")
            print(f"  Merges: {am.get('merges_applied', 0)}")
            print(f"  Atoms removed: {am.get('atoms_removed', 0)}")
            print(f"  Edges redirected: {am.get('edges_redirected', 0)}")

    except FileNotFoundError:
        print("❌ Daemon not running. Start with:")
        print("   quro cqe-daemon start")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        sys.exit(1)


@cqe_daemon_group.command(name='reload')
@click.option(
    '--socket-path',
    default='/tmp/quro_cqe.sock',
    help='Unix socket path'
)
def reload_daemon(socket_path):
    """Reload CQE index in running daemon"""
    import json

    async def _reload():
        from quro_sovereign.cqe_daemon import query_daemon

        reader, writer = await asyncio.open_unix_connection(socket_path)

        request = {"command": "reload"}
        request_data = json.dumps(request).encode()
        writer.write(request_data)
        await writer.drain()

        response_data = await reader.read(1024 * 1024)
        response = json.loads(response_data.decode())

        writer.close()
        await writer.wait_closed()

        if response.get('status') == 'reloaded':
            stats = response.get('stats', {})
            print(f"✅ Index reloaded:")
            print(f"  Atoms: {stats.get('atoms_count', 0):,}")
            print(f"  Morphisms: {stats.get('morphisms_count', 0):,}")
        else:
            print(f"❌ Reload failed: {response.get('error', 'Unknown error')}")

    try:
        asyncio.run(_reload())
    except Exception as e:
        print(f"❌ Failed to reload: {e}")
        sys.exit(1)


@cqe_daemon_group.command(name='compile')
@click.option(
    '--index-path',
    type=click.Path(),
    default='.quro_context/cqe_index.db',
    help='Path to CQE index database'
)
@click.option(
    '--output',
    type=click.Path(),
    default='.quro_context/cqe_manifold.qmf',
    help='Output .qmf file path'
)
@click.option(
    '--project-root',
    type=click.Path(exists=True),
    default='.',
    help='Project root directory'
)
def compile_manifold(index_path, output, project_root):
    """Compile CQE index to portable .qmf manifold file.

    This generates a KernelCertificate-signed .qmf file that can be:
    - Distributed across devices
    - Used for zero-LLM inference via ANERouter
    - Verified for integrity via graph hash
    """
    from pathlib import Path
    from quro_algebra.compiler import ManifoldCompiler

    try:
        compiler = ManifoldCompiler(
            index_db_path=Path(index_path),
            project_root=Path(project_root)
        )
        qmf_path = compiler.compile(output_path=Path(output))

        if qmf_path and qmf_path.exists():
            size_mb = qmf_path.stat().st_size / (1024 * 1024)
            print(f"✅ Compiled manifold to: {qmf_path}")
            print(f"   Size: {size_mb:.2f} MB")
            print(f"\n   Use with ANERouter for zero-LLM queries:")
            print(f"   - Load: ANERouter(manifold_path='{qmf_path}')")
            print(f"   - Query: router.route(symbols=['...'], tau=0.1)")
        else:
            print(f"❌ Compilation failed: output file not created")
            sys.exit(1)
    except FileNotFoundError as e:
        print(f"❌ Index not found: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Compilation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
