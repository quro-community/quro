"""Service Registry

@module quro.service.registry
@intent Central registry for all services.
"""

from typing import Dict, List, Optional

from service.base import BaseService


class ServiceRegistry:
    """Registry for all services.

    Provides centralized access to all registered services.
    Services register themselves on import.
    """

    _services: Dict[str, BaseService] = {}

    @classmethod
    def register(cls, service: BaseService) -> None:
        """Register a service.

        Args:
            service: Service instance to register

        Raises:
            ValueError: If service with same name already registered
        """
        name = service.get_name()
        if name in cls._services:
            raise ValueError(
                f"Service '{name}' is already registered. "
                f"Cannot register duplicate service."
            )
        cls._services[name] = service

    @classmethod
    def get(cls, name: str) -> BaseService:
        """Get a service by name.

        Args:
            name: Service name

        Returns:
            Service instance

        Raises:
            KeyError: If service not found
        """
        if name not in cls._services:
            available = ", ".join(cls._services.keys())
            raise KeyError(
                f"Service '{name}' not found. "
                f"Available services: {available}"
            )
        return cls._services[name]

    @classmethod
    def get_optional(cls, name: str) -> Optional[BaseService]:
        """Get a service by name, returning None if not found.

        Args:
            name: Service name

        Returns:
            Service instance or None if not found
        """
        return cls._services.get(name)

    @classmethod
    def list_services(cls) -> List[str]:
        """List all registered service names.

        Returns:
            List of service names
        """
        return list(cls._services.keys())

    @classmethod
    def get_all(cls) -> Dict[str, BaseService]:
        """Get all registered services.

        Returns:
            Dictionary mapping service names to instances
        """
        return cls._services.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered services.

        Warning: This is primarily for testing. Use with caution.
        """
        cls._services.clear()
