"""
Extension Protocol - Isolation boundary contract

@module quro.protocols.extension
@intent Enforce extension isolation invariant
@constraint Extensions cannot access kernel internals

INVARIANT: Extension is Isolated
- NO kernel imports
- NO kernel state mutation
- NO direct kernel access
- ONLY event-based communication
- ONLY explicit I/O operations
"""

from typing import Protocol, runtime_checkable, Any, Dict


@runtime_checkable
class ExtensionProtocol(Protocol):
    """
    Extension boundary contract.

    Extensions MUST be isolated from kernel internals.

    MUST NOT:
    - Import kernel modules (quro.core)
    - Access kernel state directly
    - Mutate kernel memory
    - Bypass I/O boundary
    - Call kernel functions directly

    MUST:
    - Use event-based communication only
    - Declare all I/O operations explicitly
    - Handle errors internally (no kernel pollution)
    - Be removable without breaking kernel
    """

    def mount(self, context: "ExtensionContext") -> None:
        """
        Mount extension (setup phase).

        Called once during initialization.
        Extensions can register hooks, validate config, etc.

        Args:
            context: Extension context (read-only access to config)

        Raises:
            ValueError: If extension config is invalid
        """
        ...

    def execute(self, event: "Event") -> None:
        """
        Execute on event (isolated runtime).

        Called when registered event occurs.
        Extensions MUST NOT access kernel state.

        Args:
            event: Event data (immutable)

        Raises:
            ExtensionError: If extension execution fails
        """
        ...


class ExtensionContext:
    """
    Extension context (read-only).

    Provides safe access to configuration and metadata.
    DOES NOT provide access to kernel internals.
    """

    def __init__(self, config: Dict[str, Any], workspace_root: str):
        self.config = config
        self.workspace_root = workspace_root

    # NO methods that expose kernel state


class Event:
    """
    Event data (immutable).

    Passed to extensions during execution.
    Contains only serializable data, no kernel references.
    """

    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data

    # NO methods that expose kernel state


class ExtensionError(Exception):
    """Extension execution error (isolated from kernel)"""
    pass
