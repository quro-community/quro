"""Command Registry

@module quro.cli.registry
@intent Central registry for all CLI commands.
"""

from typing import Dict, List

from cli.base import BaseCommand


class CommandRegistry:
    """Registry for all CLI commands.

    Provides centralized access to all registered commands.
    Commands register themselves on import.
    """

    _commands: Dict[str, BaseCommand] = {}

    @classmethod
    def register(cls, command: BaseCommand) -> None:
        """Register a command.

        Args:
            command: Command instance to register

        Raises:
            ValueError: If command with same name already registered
        """
        name = command.get_name()
        if name in cls._commands:
            raise ValueError(
                f"Command '{name}' is already registered. "
                f"Cannot register duplicate command."
            )
        cls._commands[name] = command

    @classmethod
    def get(cls, name: str) -> BaseCommand:
        """Get a command by name.

        Args:
            name: Command name

        Returns:
            Command instance

        Raises:
            KeyError: If command not found
        """
        if name not in cls._commands:
            available = ", ".join(cls._commands.keys())
            raise KeyError(
                f"Command '{name}' not found. "
                f"Available commands: {available}"
            )
        return cls._commands[name]

    @classmethod
    def list_commands(cls) -> List[str]:
        """List all registered command names.

        Returns:
            List of command names
        """
        return list(cls._commands.keys())

    @classmethod
    def get_all(cls) -> Dict[str, BaseCommand]:
        """Get all registered commands.

        Returns:
            Dictionary mapping command names to instances
        """
        return cls._commands.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered commands.

        Warning: This is primarily for testing. Use with caution.
        """
        cls._commands.clear()
