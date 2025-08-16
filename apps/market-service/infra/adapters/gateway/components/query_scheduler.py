"""
Query Scheduler for vnpy gateways.

Manages periodic queries and rotation of query functions.
"""

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from vnpy.trader.gateway import BaseGateway

logger = logging.getLogger(__name__)


class QueryConfig(BaseModel):
    """Configuration for query scheduling."""

    model_config = ConfigDict(strict=True)

    query_interval: int = Field(default=2, description="Query interval in seconds", gt=0)
    max_retries: int = Field(default=3, description="Max retries for failed queries", gt=0)
    retry_delay: int = Field(default=1, description="Delay between retries in seconds", gt=0)


class QueryScheduler:
    """
    Schedules and manages periodic queries to gateway.

    Responsibilities:
    - Schedule periodic queries
    - Rotate query functions
    - Handle query failures with retry
    - Track query statistics
    """

    def __init__(
        self,
        executor: ThreadPoolExecutor,
        gateway: BaseGateway | None = None,
        config: QueryConfig | dict | None = None,
    ):
        """
        Initialize query scheduler.

        Args:
            executor: Thread pool executor for vnpy operations
            gateway: vnpy gateway instance
            config: Query configuration (dict or QueryConfig object)
        """
        self.executor = executor
        self.gateway = gateway
        # Convert dict to QueryConfig if needed
        if isinstance(config, dict):
            self.config = QueryConfig(**config)
        else:
            self.config = config or QueryConfig()

        # Query functions
        self.query_functions: list[Callable] = []
        self.query_index = 0
        self.query_count = 0

        # Query results storage
        self.accounts: dict[str, Any] = {}
        self.positions: list[Any] = []

        # Scheduler task
        self._scheduler_task: asyncio.Task | None = None
        self._main_loop: asyncio.AbstractEventLoop | None = None

        # Statistics
        self.query_stats: dict[str, int] = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "retried": 0,
        }

    def set_gateway(self, gateway: BaseGateway) -> None:
        """Set gateway instance."""
        self.gateway = gateway
        self._setup_query_functions()

    def _setup_query_functions(self) -> None:
        """Setup default query functions."""
        if not self.gateway:
            return

        self.query_functions = [
            lambda: self.gateway.query_account() if self.gateway else None,
            lambda: self.gateway.query_position() if self.gateway else None,
        ]

        logger.info(f"Setup {len(self.query_functions)} query functions")

    def add_query_function(self, func: Callable) -> None:
        """
        Add a custom query function.

        Args:
            func: Query function to add
        """
        self.query_functions.append(func)
        logger.debug(f"Added query function, total: {len(self.query_functions)}")

    def clear_query_functions(self) -> None:
        """Clear all query functions."""
        self.query_functions.clear()
        self.query_index = 0
        logger.debug("Cleared all query functions")

    async def start(self) -> None:
        """Start the query scheduler."""
        if self._scheduler_task:
            logger.warning("Query scheduler already running")
            return

        self._main_loop = asyncio.get_event_loop()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Query scheduler started")

    async def stop(self) -> None:
        """Stop the query scheduler."""
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None
            logger.info("Query scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while True:
            try:
                await asyncio.sleep(self.config.query_interval)

                if self.query_functions and self.gateway:
                    await self._execute_next_query()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")

    async def _execute_next_query(self) -> None:
        """Execute the next query function in rotation."""
        if not self.query_functions:
            return

        # Get next function
        func = self.query_functions[self.query_index]
        self.query_index = (self.query_index + 1) % len(self.query_functions)
        self.query_count += 1

        # Execute with retry
        for attempt in range(self.config.max_retries):
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self.executor, func)

                self.query_stats["total"] += 1
                self.query_stats["success"] += 1

                logger.debug(f"Query executed successfully (count: {self.query_count})")
                break

            except Exception as e:
                logger.error(f"Query attempt {attempt + 1} failed: {e}")
                self.query_stats["failed"] += 1

                if attempt < self.config.max_retries - 1:
                    self.query_stats["retried"] += 1
                    await asyncio.sleep(self.config.retry_delay)

    async def query_account(self) -> dict[str, Any]:
        """
        Query account information.

        Returns:
            Dictionary with account information
        """
        if not self.gateway:
            raise ValueError("Gateway not set")

        loop = asyncio.get_event_loop()

        # Clear existing data
        self.accounts.clear()

        # Execute query
        await loop.run_in_executor(self.executor, self.gateway.query_account)

        # Wait for response
        await asyncio.sleep(1)

        return self.accounts

    async def query_position(self) -> list[Any]:
        """
        Query position information.

        Returns:
            List of positions
        """
        if not self.gateway:
            raise ValueError("Gateway not set")

        loop = asyncio.get_event_loop()

        # Clear existing data
        self.positions.clear()

        # Execute query
        await loop.run_in_executor(self.executor, self.gateway.query_position)

        # Wait for response
        await asyncio.sleep(1)

        return self.positions

    def update_account(self, account_data: dict[str, Any]) -> None:
        """
        Update account data from event.

        Args:
            account_data: Account information
        """
        account_id = account_data.get("account_id", "default")
        self.accounts[account_id] = account_data
        logger.debug(f"Updated account: {account_id}")

    def update_position(self, position_data: dict[str, Any]) -> None:
        """
        Update position data from event.

        Args:
            position_data: Position information
        """
        # Find existing position
        symbol = position_data.get("symbol")
        direction = position_data.get("direction")

        # Update or append
        updated = False
        for i, pos in enumerate(self.positions):
            if pos.get("symbol") == symbol and pos.get("direction") == direction:
                self.positions[i] = position_data
                updated = True
                break

        if not updated:
            self.positions.append(position_data)

        logger.debug(f"Updated position: {symbol} {direction}")

    def get_statistics(self) -> dict[str, int]:
        """
        Get query statistics.

        Returns:
            Dictionary with query statistics
        """
        return self.query_stats.copy()

    def reset_statistics(self) -> None:
        """Reset query statistics."""
        self.query_stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "retried": 0,
        }
        logger.debug("Reset query statistics")
