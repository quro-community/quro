#!/usr/bin/env python3
"""
TypeScript Probe Integration Example

Demonstrates the TypeScript probe analyzing a real file from node_server.
"""
import asyncio
from pathlib import Path
from quro_cli.analysis.typescript_analyzer import TypeScriptAnalyzer


async def main():
    """Run integration example"""
    workspace_root = Path(__file__).parent.parent.parent
    tsconfig_path = workspace_root / "node_server" / "tsconfig.json"

    if not tsconfig_path.exists():
        print("❌ node_server/tsconfig.json not found")
        return

    print("🚀 Starting TypeScript Analyzer...")
    print()

    async with TypeScriptAnalyzer(str(workspace_root), str(tsconfig_path)) as analyzer:
        # Health check
        health = await analyzer.health_check()
        print(f"✅ Analyzer initialized")
        print(f"   Probe available: {health['probe_available']}")
        if health.get('probe_alive'):
            print(f"   Probe alive: {health['probe_alive']}")
        print()

        # Analyze a real file
        test_file = workspace_root / "node_server" / "lib" / "registry.ts"

        if not test_file.exists():
            print(f"❌ Test file not found: {test_file}")
            return

        print(f"📄 Analyzing: {test_file.name}")
        print()

        # Get diagnostics
        print("🔍 Running diagnostics...")
        diagnostics = await analyzer.get_diagnostics(str(test_file))

        if diagnostics:
            print(f"   Found {len(diagnostics)} diagnostic(s):")
            for diag in diagnostics[:5]:  # Show first 5
                loc = diag.location
                loc_str = f":{loc['line']}:{loc['character']}" if loc else ""
                print(f"   [{diag.category}] {diag.message}{loc_str}")
        else:
            print("   ✅ No diagnostics (file is clean)")
        print()

        # Try to get symbol at a position
        print("🔎 Getting symbol at position (line 10, char 10)...")
        symbol = await analyzer.get_symbol_at_position(str(test_file), 10, 10)

        if symbol:
            print(f"   ✅ Found symbol: {symbol.name}")
            print(f"      Kind: {symbol.kind}")
            print(f"      Type: {symbol.type_string or 'N/A'}")
            print(f"      Source: {symbol.source}")
            if symbol.fingerprint:
                print(f"      Fingerprint: {symbol.fingerprint}")
        else:
            print("   ℹ️  No symbol at this position")
        print()

        # Try to resolve an import
        print("🔗 Resolving import './types'...")
        resolved = await analyzer.resolve_import(str(test_file), "./types")

        if resolved:
            print(f"   ✅ Resolved to: {Path(resolved).name}")
        else:
            print("   ℹ️  Import not found or external module")
        print()

        print("✨ Integration example complete!")


if __name__ == "__main__":
    asyncio.run(main())
