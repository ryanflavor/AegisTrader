"""
Gateway Adapter using component-based architecture.

Clean, component-based design following Single Responsibility Principle
and Domain-Driven Design patterns.
"""

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import CancelRequest, OrderRequest, SubscribeRequest

from domain.gateway.ports import GatewayPort
from domain.gateway.value_objects import AuthenticationCredentials

from .anti_corruption import LocaleManager, VnpyEventAdapter, VnpyTranslator
from .components import ConnectionManager, EventDispatcher, QueryScheduler

logger = logging.getLogger(__name__)


class GatewayAdapterConfig(BaseModel):
    """Configuration for gateway adapter."""

    model_config = ConfigDict(strict=True)

    # Thread pool settings
    max_workers: int = Field(default=4, description="Max workers for thread pool", gt=0)

    # Connection settings
    reconnect_interval: int = Field(default=5, description="Reconnect interval in seconds", gt=0)
    max_reconnect_attempts: int = Field(default=3, description="Max reconnect attempts", gt=0)
    heartbeat_interval: int = Field(default=30, description="Heartbeat interval in seconds", gt=0)
    enable_flow_control: bool = Field(default=True, description="Enable flow control handling")

    # Query settings
    query_interval: int = Field(default=2, description="Query interval in seconds", gt=0)

    # Initialization settings
    contract_init_threshold: int = Field(
        default=100, description="Contracts needed for initialization", gt=0
    )


class GatewayAdapter(GatewayPort):
    """
    Gateway adapter using component-based architecture.

    This facade coordinates multiple focused components:
    - LocaleManager: Handles Chinese locale requirements
    - ConnectionManager: Manages connection lifecycle
    - EventDispatcher: Routes and translates events
    - QueryScheduler: Manages periodic queries
    - VnpyTranslator: Translates between vnpy and domain objects
    - VnpyEventAdapter: Bridges sync/async event systems
    """

    def __init__(self, config: GatewayAdapterConfig | None = None):
        """
        Initialize refactored gateway adapter.

        Args:
            config: Gateway adapter configuration
        """
        self.config = config or GatewayAdapterConfig()

        # Setup Chinese locale for vnpy
        LocaleManager.setup_chinese_locale()

        # Create thread pool executor
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.max_workers, thread_name_prefix="vnpy_"
        )

        # Initialize anti-corruption layer
        self.translator = VnpyTranslator()
        self.event_adapter = VnpyEventAdapter()

        # Initialize components
        self.connection_manager = ConnectionManager(
            self.executor,
            config={
                "reconnect_interval": self.config.reconnect_interval,
                "max_reconnect_attempts": self.config.max_reconnect_attempts,
                "heartbeat_interval": self.config.heartbeat_interval,
                "enable_flow_control": self.config.enable_flow_control,
            },
        )

        self.event_dispatcher = EventDispatcher(self.event_adapter, self.translator)

        self.query_scheduler = QueryScheduler(
            self.executor,
            config={
                "query_interval": self.config.query_interval,
            },
        )

        # Tracking
        self.subscribed_symbols: set[str] = set()

        # Gateway identification (to be set by subclass)
        self.gateway_name: str = ""
        self.gateway_class: type[BaseGateway] | None = None

        logger.info("Initialized gateway adapter")

    def set_gateway_info(self, name: str, gateway_class: type[BaseGateway]) -> None:
        """
        Set gateway information.

        Args:
            name: Gateway name
            gateway_class: Gateway class type
        """
        self.gateway_name = name
        self.gateway_class = gateway_class
        self.connection_manager.set_gateway_info(name, gateway_class)

    def _prepare_connection_setting(self, credentials: AuthenticationCredentials) -> dict[str, Any]:
        """
        Prepare connection settings for vnpy.

        Args:
            credentials: Authentication credentials

        Returns:
            Dictionary with vnpy connection settings
        """
        # This should be overridden by specific gateway implementations
        return {
            "用户名": credentials.user_id,
            "密码": credentials.password,
        }

    async def connect(self, credentials: AuthenticationCredentials | None = None) -> None:
        """
        Connect to gateway.

        Args:
            credentials: Authentication credentials
        """
        if not credentials:
            raise ValueError("Credentials required for connection")

        if not self.gateway_class:
            raise ValueError("Gateway class not set")

        # Set main loop for event adapter
        loop = asyncio.get_event_loop()
        self.event_adapter.set_main_loop(loop)

        # Prepare connection settings
        setting = self._prepare_connection_setting(credentials)

        # Connect via connection manager
        await self.connection_manager.connect(credentials, setting)

        # Setup event dispatcher with event engine
        if self.connection_manager.event_engine:
            self.event_dispatcher.register_with_engine(self.connection_manager.event_engine)

        # Setup query scheduler with gateway
        if self.connection_manager.gateway:
            self.query_scheduler.set_gateway(self.connection_manager.gateway)
            await self.query_scheduler.start()

        logger.info(f"Connected to {self.gateway_name}")

    async def disconnect(self) -> None:
        """Disconnect from gateway."""
        # Stop query scheduler
        await self.query_scheduler.stop()

        # Clear event dispatcher
        self.event_dispatcher.clear_callbacks()
        self.event_dispatcher.clear_buffers()

        # Clear event adapter
        self.event_adapter.clear_queues()

        # Disconnect via connection manager
        await self.connection_manager.disconnect()

        # Clear tracking
        self.subscribed_symbols.clear()

        logger.info(f"Disconnected from {self.gateway_name}")

    async def subscribe(self, symbols: list[str] | str) -> bool:
        """
        Subscribe to market data.

        Args:
            symbols: Symbol or list of symbols to subscribe

        Returns:
            True if subscription successful, False otherwise
        """
        if not self.connection_manager.gateway:
            logger.error("Gateway not connected")
            return False

        # Convert single symbol to list
        if isinstance(symbols, str):
            symbols = [symbols]

        loop = asyncio.get_event_loop()
        success_count = 0

        for symbol in symbols:
            # Parse symbol
            parts = symbol.split(".")
            symbol_code = parts[0]

            # Get exchange
            if len(parts) > 1:
                exchange_str = parts[1]
                # Let translator handle exchange mapping
                _, exchange = self.translator.from_domain_symbol(
                    type("Symbol", (), {"value": symbol_code, "exchange": exchange_str})()
                )
            else:
                from vnpy.trader.constant import Exchange

                exchange = Exchange.SHFE

            # Create subscribe request
            req = SubscribeRequest(symbol=symbol_code, exchange=exchange)

            # Subscribe with flow control
            max_attempts = 3 if self.config.enable_flow_control else 1
            subscribed = False

            for attempt in range(max_attempts):
                try:
                    await loop.run_in_executor(
                        self.executor, self.connection_manager.gateway.subscribe, req
                    )
                    self.subscribed_symbols.add(symbol)
                    logger.info(f"Subscribed to {symbol}")
                    subscribed = True
                    success_count += 1
                    break
                except Exception as e:
                    logger.error(f"Subscribe {symbol} attempt {attempt + 1} failed: {e}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(0.5)

            if not subscribed:
                logger.error(f"Failed to subscribe to {symbol} after {max_attempts} attempts")

        return success_count > 0

    async def unsubscribe(self, symbols: list[str]) -> None:
        """
        Unsubscribe from market data.

        Args:
            symbols: List of symbols to unsubscribe
        """
        for symbol in symbols:
            self.subscribed_symbols.discard(symbol)
        logger.info(f"Unsubscribed from {len(symbols)} symbols")

    def is_connected(self) -> bool:
        """Check if gateway is connected."""
        return self.connection_manager.is_connected()

    async def send_heartbeat(self) -> None:
        """Send heartbeat."""
        # Heartbeat is handled by connection manager
        pass

    async def query_account(self) -> dict[str, Any]:
        """Query account information."""
        return await self.query_scheduler.query_account()

    async def query_position(self) -> list[Any]:
        """Query position information."""
        return await self.query_scheduler.query_position()

    async def send_order(self, order_request: dict[str, Any]) -> str:
        """
        Send order.

        Args:
            order_request: Order request parameters

        Returns:
            Order ID
        """
        if not self.connection_manager.gateway:
            raise ConnectionError("Gateway not connected")

        # Parse order request and create vnpy OrderRequest
        from vnpy.trader.constant import Direction, Exchange, Offset, OrderType

        req = OrderRequest(
            symbol=order_request["symbol"],
            exchange=Exchange[order_request.get("exchange", "SHFE")],
            direction=Direction.LONG if order_request.get("side") == "BUY" else Direction.SHORT,
            type=OrderType[order_request.get("order_type", "LIMIT")],
            volume=order_request["quantity"],
            price=order_request.get("price", 0.0),
            offset=Offset[order_request.get("offset", "OPEN")],
        )

        loop = asyncio.get_event_loop()
        order_id = await loop.run_in_executor(
            self.executor, self.connection_manager.gateway.send_order, req
        )

        logger.info(f"Order sent: {order_id}")
        return order_id

    async def cancel_order(self, order_id: str, symbol: str, exchange: str = "SHFE") -> None:
        """
        Cancel order.

        Args:
            order_id: Order ID
            symbol: Symbol
            exchange: Exchange name
        """
        if not self.connection_manager.gateway:
            raise ConnectionError("Gateway not connected")

        from vnpy.trader.constant import Exchange

        req = CancelRequest(
            orderid=order_id,
            symbol=symbol,
            exchange=Exchange[exchange],
        )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, self.connection_manager.gateway.cancel_order, req)

        logger.info(f"Order cancelled: {order_id}")

    def register_tick_callback(self, callback: Callable) -> None:
        """Register callback for tick events."""
        self.event_dispatcher.register_tick_callback(callback)

    def register_order_callback(self, callback: Callable) -> None:
        """Register callback for order events."""
        self.event_dispatcher.register_order_callback(callback)

    def register_trade_callback(self, callback: Callable) -> None:
        """Register callback for trade events."""
        self.event_dispatcher.register_trade_callback(callback)

    async def get_tick(self, timeout: float = 1.0) -> Any | None:
        """Get next tick from queue."""
        vnpy_tick = await self.event_adapter.get_tick(timeout)
        if vnpy_tick:
            tick, depth = self.translator.to_domain_tick(vnpy_tick)
            # Return just the tick for now, depth can be handled separately if needed
            return tick
        return None

    async def get_order(self, timeout: float = 1.0) -> Any | None:
        """Get next order from queue."""
        vnpy_order = await self.event_adapter.get_order(timeout)
        if vnpy_order:
            return self.translator.to_domain_order(vnpy_order)
        return None

    async def get_trade(self, timeout: float = 1.0) -> Any | None:
        """Get next trade from queue."""
        vnpy_trade = await self.event_adapter.get_trade(timeout)
        if vnpy_trade:
            return self.translator.to_domain_trade(vnpy_trade)
        return None

    async def get_connection_status(self) -> dict[str, Any]:
        """Get detailed connection status."""
        status = self.connection_manager.get_status()
        status.update(
            {
                "subscribed_symbols": list(self.subscribed_symbols),
                "query_stats": self.query_scheduler.get_statistics(),
                "event_stats": self.event_adapter.get_statistics(),
            }
        )
        return status

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info(f"Shutting down {self.gateway_name} gateway")

        try:
            # Unsubscribe all symbols
            if self.subscribed_symbols:
                await self.unsubscribe(list(self.subscribed_symbols))

            # Disconnect
            await self.disconnect()

            # Shutdown executor
            self.executor.shutdown(wait=True)

            logger.info(f"{self.gateway_name} gateway shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            raise
