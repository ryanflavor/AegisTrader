"""
Event adapter for vnpy events.

Bridges vnpy's event system to our async domain event system.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from vnpy.event import Event
from vnpy.trader.event import (
    EVENT_ACCOUNT,
    EVENT_CONTRACT,
    EVENT_ORDER,
    EVENT_POSITION,
    EVENT_TICK,
    EVENT_TRADE,
)

logger = logging.getLogger(__name__)


class VnpyEventAdapter:
    """
    Adapts vnpy events to domain events.

    This adapter bridges vnpy's synchronous event system with our
    async domain event handlers using thread-safe queues.
    """

    def __init__(self, main_loop: asyncio.AbstractEventLoop | None = None):
        """
        Initialize event adapter.

        Args:
            main_loop: Main asyncio event loop for thread-safe operations
        """
        self._main_loop = main_loop

        # Event queues for async processing
        self.contract_queue: asyncio.Queue = asyncio.Queue()
        self.tick_queue: asyncio.Queue = asyncio.Queue()
        self.order_queue: asyncio.Queue = asyncio.Queue()
        self.trade_queue: asyncio.Queue = asyncio.Queue()
        self.position_queue: asyncio.Queue = asyncio.Queue()
        self.account_queue: asyncio.Queue = asyncio.Queue()

        # Event handlers mapping
        self._handlers: dict[str, Callable] = {}

        # Statistics
        self.event_counts: dict[str, int] = {}

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the main event loop for thread-safe operations."""
        self._main_loop = loop

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """
        Register a handler for specific event type.

        Args:
            event_type: vnpy event type constant
            handler: Handler function to call
        """
        self._handlers[event_type] = handler
        logger.debug(f"Registered handler for {event_type}")

    def handle_event(self, event: Event) -> None:
        """
        Handle vnpy event in sync context.

        This is called from vnpy's thread and needs to be thread-safe.

        Args:
            event: vnpy Event object
        """
        event_type = event.type

        # Update statistics
        self.event_counts[event_type] = self.event_counts.get(event_type, 0) + 1

        # Get specific handler if registered
        if event_type in self._handlers:
            try:
                self._handlers[event_type](event)
            except Exception as e:
                logger.error(f"Error in handler for {event_type}: {e}")

        # Queue event for async processing if main loop available
        if self._main_loop:
            self._queue_event_async(event)

    def _queue_event_async(self, event: Event) -> None:
        """
        Queue event for async processing.

        Uses thread-safe method to queue events from vnpy thread.
        """
        queue = self._get_queue_for_event(event.type)
        if queue and event.data:
            try:
                asyncio.run_coroutine_threadsafe(queue.put(event.data), self._main_loop)
            except Exception as e:
                logger.debug(f"Error queuing {event.type}: {e}")

    def _get_queue_for_event(self, event_type: str) -> asyncio.Queue | None:
        """Get the appropriate queue for event type."""
        queue_map = {
            EVENT_CONTRACT: self.contract_queue,
            EVENT_TICK: self.tick_queue,
            EVENT_ORDER: self.order_queue,
            EVENT_TRADE: self.trade_queue,
            EVENT_POSITION: self.position_queue,
            EVENT_ACCOUNT: self.account_queue,
        }
        return queue_map.get(event_type)

    async def get_tick(self, timeout: float = 1.0) -> Any | None:
        """
        Get next tick from queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Tick data or None if timeout
        """
        try:
            return await asyncio.wait_for(self.tick_queue.get(), timeout)
        except TimeoutError:
            return None

    async def get_order(self, timeout: float = 1.0) -> Any | None:
        """
        Get next order from queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Order data or None if timeout
        """
        try:
            return await asyncio.wait_for(self.order_queue.get(), timeout)
        except TimeoutError:
            return None

    async def get_trade(self, timeout: float = 1.0) -> Any | None:
        """
        Get next trade from queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Trade data or None if timeout
        """
        try:
            return await asyncio.wait_for(self.trade_queue.get(), timeout)
        except TimeoutError:
            return None

    async def get_position(self, timeout: float = 1.0) -> Any | None:
        """
        Get next position from queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Position data or None if timeout
        """
        try:
            return await asyncio.wait_for(self.position_queue.get(), timeout)
        except TimeoutError:
            return None

    async def get_account(self, timeout: float = 1.0) -> Any | None:
        """
        Get next account from queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Account data or None if timeout
        """
        try:
            return await asyncio.wait_for(self.account_queue.get(), timeout)
        except TimeoutError:
            return None

    async def get_contract(self, timeout: float = 1.0) -> Any | None:
        """
        Get next contract from queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Contract data or None if timeout
        """
        try:
            return await asyncio.wait_for(self.contract_queue.get(), timeout)
        except TimeoutError:
            return None

    def get_statistics(self) -> dict[str, int]:
        """Get event processing statistics."""
        return self.event_counts.copy()

    def clear_queues(self) -> None:
        """Clear all event queues."""
        # Create new queues to clear
        self.contract_queue = asyncio.Queue()
        self.tick_queue = asyncio.Queue()
        self.order_queue = asyncio.Queue()
        self.trade_queue = asyncio.Queue()
        self.position_queue = asyncio.Queue()
        self.account_queue = asyncio.Queue()

        logger.debug("Cleared all event queues")
