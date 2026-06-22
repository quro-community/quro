"""Base Service Class

@module quro.service.base
@intent Define base interface for all services.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class BaseService(ABC):
    """Base class for all services.

    All services must implement this interface to be registered
    and used by CLI, MCP, and programmatic API.
    """

    def __init__(self):
        """Initialize service."""
        self._workspace_root: Path | None = None
        self._initialized = False

    @abstractmethod
    def get_name(self) -> str:
        """Return service name.

        Returns:
            Service name (e.g., "cqe", "tda", "scanner")
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Return service description.

        Returns:
            Human-readable description of service
        """
        pass

    @abstractmethod
    def initialize(self, workspace_root: Path) -> None:
        """Initialize service with workspace.

        Args:
            workspace_root: Path to workspace root directory

        Raises:
            ValueError: If workspace is invalid
            RuntimeError: If initialization fails
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return service capabilities.

        Returns:
            Dictionary describing service capabilities, methods, and metadata
        """
        pass

    def is_initialized(self) -> bool:
        """Check if service is initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    def get_workspace_root(self) -> Path | None:
        """Get workspace root path.

        Returns:
            Workspace root path if initialized, None otherwise
        """
        return self._workspace_root

    def _ensure_initialized(self) -> None:
        """Ensure service is initialized.

        Raises:
            RuntimeError: If service is not initialized
        """
        if not self._initialized:
            raise RuntimeError(
                f"Service '{self.get_name()}' is not initialized. "
                f"Call initialize() first."
            )
