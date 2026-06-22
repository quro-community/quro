"""Base Command Class

@module quro.cli.base
@intent Define base interface for all CLI commands.
"""

import argparse
from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """Base class for all CLI commands.

    All commands must implement this interface to be registered
    and used by the CLI.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return command name.

        Returns:
            Command name (e.g., "scan", "query", "plan")
        """
        pass

    @abstractmethod
    def get_help(self) -> str:
        """Return command help text.

        Returns:
            Short help text describing the command
        """
        pass

    @abstractmethod
    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        """Configure argument parser for this command.

        Args:
            parser: Argument parser to configure
        """
        pass

    @abstractmethod
    def execute(self, args: argparse.Namespace) -> int:
        """Execute command.

        Args:
            args: Parsed command-line arguments

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        pass
