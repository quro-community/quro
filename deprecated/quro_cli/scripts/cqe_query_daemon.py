#!/usr/bin/env python3
"""
CQE Query via Daemon - Fast query using always-running daemon

@module quro_cli.scripts.cqe_query_daemon
@intent Provide fast CQE queries via Unix socket daemon

Usage:
    python -m quro_cli.scripts.cqe_query_daemon "query text" entry_token [tau] [max_depth]

Example:
    python -m quro_cli.scripts.cqe_query_daemon "hash functions" hash 0.0 2

Note: entry_token should be just the token (e.g., "hash", "async"), not the full ID (e.g., "cat::hash")
"""
import asyncio
import sys

from quro_sovereign.cqe_daemon import query_daemon


async def main():
    if len(sys.argv) < 3:
        print("Usage: python -m quro_cli.scripts.cqe_query_daemon <query> <entry_token> [tau] [max_depth]")
        print()
        print("Example:")
        print("  python -m quro_cli.scripts.cqe_query_daemon \"hash functions\" hash 0.0 2")
        print()
        print("Note: entry_token should be just the token (e.g., 'hash', 'async'), not the full ID")
        sys.exit(1)

    query = sys.argv[1]
    entry_token = sys.argv[2]
    tau = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
    max_depth = int(sys.argv[4]) if len(sys.argv) > 4 else 3

    print(f"🔍 CQE Query via Daemon")
    print(f"  Query: {query}")
    print(f"  Entry: {entry_token}")
    print(f"  Tau: {tau}")
    print(f"  Max depth: {max_depth}")
    print()

    try:
        result = await query_daemon(
            query=query,
            entry_token=entry_token,
            tau=tau,
            max_depth=max_depth
        )

        if result.get('status') == 'success':
            print(f"✅ Query successful")
            print(f"  Nodes visited: {result.get('nodes_visited', 0)}")
            print(f"  Results: {len(result.get('results', []))}")
            print()
            print("📊 Top Results:")
            for i, res in enumerate(result.get('results', [])[:10], 1):
                print(f"  {i}. {res['atom_id']} (MI: {res['mi_score']:.3f}, depth: {res['depth']})")
        else:
            print(f"❌ Query failed: {result.get('error', 'Unknown error')}")

    except (FileNotFoundError, ConnectionRefusedError) as e:
        print("❌ Daemon not running. Start it with:")
        print("   quro cqe-daemon start")
        print()
        print("Or use the direct query script:")
        print("   python scripts/cqe_query.py \"hash functions\" cat::hash 0.0 2")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Query failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
