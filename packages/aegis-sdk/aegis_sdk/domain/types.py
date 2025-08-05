"""Type definitions and protocols for strong typing across the SDK.

This module provides Protocol classes and type aliases to ensure
type safety when working with handlers and callbacks.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from .models import Command, Event


class EventHandler(Protocol):
    """Protocol for event handlers.

    Event handlers receive an Event and perform async processing.
    They should not return any value.
    """

    async def __call__(self, event: Event) -> None:
        """Handle an event.

        Args:
            event: The event to handle
        """
        ...


class RPCHandler(Protocol):
    """Protocol for RPC method handlers.

    RPC handlers receive parameters and return a response.
    Both params and response must be JSON-serializable.
    """

    async def __call__(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle an RPC request.

        Args:
            params: Request parameters

        Returns:
            Response data as a dictionary
        """
        ...


class CommandHandler(Protocol):
    """Protocol for command handlers.

    Command handlers receive a command and a progress callback.
    They can report progress and must return a result.
    """

    async def __call__(
        self, command: Command, progress: Callable[[float, str], Awaitable[None]]
    ) -> dict[str, Any]:
        """Handle a command.

        Args:
            command: The command to execute
            progress: Async callback to report progress (percentage, message)

        Returns:
            Command execution result
        """
        ...


# Type aliases for common patterns
ProgressCallback = Callable[[float, str], Awaitable[None]]
"""Progress callback type: (percentage: float, message: str) -> Awaitable[None]"""

MessageHandler = EventHandler | RPCHandler | CommandHandler
"""Union type for any message handler"""
