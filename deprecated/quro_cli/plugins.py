"""
Quro CLI Plugin System - Dynamic command registration and discovery

@module quro_cli.plugins
@intent Enable dynamic command registration without modifying main.py

Architecture:
  1. Plugin Discovery: Auto-discover plugins in quro_cli/commands/
  2. Command Registration: Each plugin registers its Click commands
  3. Metadata: Each command has docstring + usage examples
  4. Indexing: Generate command index for Claude to search

Plugin Structure:
  quro_cli/commands/
    ├── __init__.py          # Plugin loader
    ├── cqe_commands.py      # CQE-related commands
    ├── mi_commands.py       # MI-path training commands
    └── scan_commands.py     # Workspace scanning commands

Each plugin exports:
  - register(cli): Function to register Click commands
  - METADATA: Dict with command descriptions and examples
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List, Callable
import click


class PluginRegistry:
    """Registry for dynamically discovered CLI plugins"""

    def __init__(self):
        self.plugins: Dict[str, Dict] = {}
        self.commands: Dict[str, Callable] = {}

    def discover_plugins(self, package_name: str = 'quro_cli.commands'):
        """
        Discover all plugins in quro_cli/commands/

        Args:
            package_name: Package to scan for plugins (default: quro_cli.commands)
        """
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            return

        # Scan for plugin modules
        for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
            if modname.startswith('_'):
                continue

            full_name = f"{package_name}.{modname}"
            try:
                module = importlib.import_module(full_name)

                # Check if module has register function
                if hasattr(module, 'register'):
                    self.plugins[modname] = {
                        'module': module,
                        'metadata': getattr(module, 'METADATA', {}),
                        'register': module.register
                    }
            except Exception as e:
                click.echo(f"⚠️  Failed to load plugin {modname}: {e}", err=True)

    def register_all(self, cli: click.Group):
        """
        Register all discovered plugins with Click CLI

        Args:
            cli: Click group to register commands to
        """
        for plugin_name, plugin_info in self.plugins.items():
            try:
                plugin_info['register'](cli)
            except Exception as e:
                click.echo(f"⚠️  Failed to register plugin {plugin_name}: {e}", err=True)

    def generate_index(self, output_path: Path):
        """
        Generate command index for Claude to search

        Args:
            output_path: Path to save index (e.g., .quro_context/command_index.md)
        """
        lines = []
        lines.append("# Quro CLI Command Index")
        lines.append("\n**Auto-generated command reference for Claude Code**\n")
        lines.append("---\n")

        for plugin_name, plugin_info in sorted(self.plugins.items()):
            metadata = plugin_info['metadata']

            lines.append(f"## Plugin: {plugin_name}\n")

            if 'description' in metadata:
                lines.append(f"{metadata['description']}\n")

            if 'commands' in metadata:
                for cmd_name, cmd_info in metadata['commands'].items():
                    lines.append(f"### `quro {cmd_name}`\n")
                    lines.append(f"**Description:** {cmd_info.get('description', 'No description')}\n")

                    if 'usage' in cmd_info:
                        lines.append(f"**Usage:**\n```bash\n{cmd_info['usage']}\n```\n")

                    if 'implementation' in cmd_info:
                        lines.append(f"**Implementation:** `{cmd_info['implementation']}`\n")

                    lines.append("")

        # Save index
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        click.echo(f"✅ Command index saved to: {output_path}")


# Global registry instance
_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get global plugin registry"""
    return _registry
