"""CLI Module for Quro v3

@module quro.cli
@intent Command-line interface for Quro v3.

Provides a unified CLI with register-based command architecture.
"""

from cli.base import BaseCommand
from cli.registry import CommandRegistry

__all__ = [
    "BaseCommand",
    "CommandRegistry",
]
