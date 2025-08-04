"""Pricing Service implementation using AegisSDK."""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from typing import Any

from aegis_sdk.application import Service
from aegis_sdk.domain.models import Event
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.ports.logger import LoggerPort
from aegis_sdk.ports.message_bus import MessageBusPort
from aegis_sdk.ports.metrics import MetricsPort
from aegis_sdk.ports.service_discovery import ServiceDiscoveryPort
from aegis_sdk.ports.service_registry import ServiceRegistryPort
from shared_contracts import EventPatterns, RPCPatterns, ServiceNames, parse_event_pattern


class PricingService(Service):
    """Example pricing data service."""

    def __init__(
        self,
        message_bus: MessageBusPort,
        instance_id: str | None = None,
        version: str = "1.0.0",
        service_registry: ServiceRegistryPort | None = None,
        service_discovery: ServiceDiscoveryPort | None = None,
        logger: LoggerPort | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize pricing service."""
        super().__init__(
            service_name=ServiceNames.PRICING_SERVICE,
            message_bus=message_bus,
            instance_id=instance_id,
            version=version,
            service_registry=service_registry,
            service_discovery=service_discovery,
            logger=logger,
        )

        # Simulated market data
        self._base_prices = {
            "AAPL": 175.0,
            "GOOGL": 140.0,
            "MSFT": 380.0,
            "AMZN": 170.0,
            "TSLA": 250.0,
            "BTC": 45000.0,
            "ETH": 2500.0,
        }

        self._price_update_task: asyncio.Task | None = None

        # Metrics
        self._metrics = metrics or InMemoryMetrics()

    async def on_start(self) -> None:
        """Register RPC handlers on service start."""

        # Register RPC methods
        @self.rpc(RPCPatterns.ECHO)
        async def echo(params: dict[str, Any]) -> dict[str, Any]:
            """Echo the input parameters."""
            self._metrics.increment("rpc.echo.calls")
            return {
                "echo": params,
                "service": self.service_name,
                "instance": self.instance_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        @self.rpc(RPCPatterns.HEALTH)
        async def health(params: dict[str, Any]) -> dict[str, Any]:
            """Return service health status."""
            self._metrics.increment("rpc.health.calls")
            self._metrics.gauge("prices.symbols_tracked", len(self._base_prices))
            return {
                "status": "healthy",
                "service": self.service_name,
                "instance": self.instance_id,
                "uptime": (
                    (datetime.now(UTC) - self._start_time).total_seconds()
                    if self._start_time
                    else 0
                ),
                "price_symbols": len(self._base_prices),
                "metrics": self._metrics.get_all(),
            }

        @self.rpc(RPCPatterns.SIMULATE_WORK)
        async def simulate_work(params: dict[str, Any]) -> dict[str, Any]:
            """Simulate processing work."""
            duration = params.get("duration", 1.0)
            await asyncio.sleep(duration)
            return {
                "work_completed": True,
                "duration": duration,
                "service": self.service_name,
                "instance": self.instance_id,
            }

        @self.rpc("get_price")
        async def get_price(params: dict[str, Any]) -> dict[str, Any]:
            """Get current price for a symbol."""
            with self._metrics.timer("rpc.get_price.duration_ms"):
                self._metrics.increment("prices.requests")
                symbol = params.get("symbol")
                if not symbol:
                    raise ValueError("symbol is required")

                # Get base price or default
                base_price = self._base_prices.get(symbol, 100.0)

                # Add some random variation (-2% to +2%)
                variation = random.uniform(0.98, 1.02)  # nosec
                current_price = round(base_price * variation, 2)

                return {
                    "symbol": symbol,
                    "price": current_price,
                    "bid": round(current_price * 0.999, 2),
                    "ask": round(current_price * 1.001, 2),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "instance": self.instance_id,
                }

        @self.rpc("get_prices")
        async def get_prices(params: dict[str, Any]) -> dict[str, Any]:
            """Get prices for multiple symbols."""
            symbols = params.get("symbols", [])
            if not symbols:
                symbols = list(self._base_prices.keys())

            prices = {}
            for symbol in symbols:
                result = await get_price({"symbol": symbol})
                prices[symbol] = {
                    "price": result["price"],
                    "bid": result["bid"],
                    "ask": result["ask"],
                }

            return {
                "prices": prices,
                "timestamp": datetime.now(UTC).isoformat(),
                "instance": self.instance_id,
            }

        @self.rpc("subscribe_price_updates")
        async def subscribe_price_updates(params: dict[str, Any]) -> dict[str, Any]:
            """Subscribe to price updates (simulated)."""
            symbols = params.get("symbols", [])
            if not symbols:
                raise ValueError("symbols are required")

            # In a real system, this would set up a subscription
            # For demo, we just acknowledge
            return {
                "subscribed": True,
                "symbols": symbols,
                "message": "Price updates will be published to trading.price.* events",
                "instance": self.instance_id,
            }

        # Subscribe to order events to provide pricing
        @self.subscribe(EventPatterns.ORDER_CREATED)
        async def handle_order_created(event: Event) -> None:
            """Provide pricing for new orders."""
            order = event.payload.get("order", {})
            symbol = order.get("symbol")

            if symbol:
                # Get current price
                price_data = await get_price({"symbol": symbol})

                # Emit price quote event
                domain, event_type = parse_event_pattern(EventPatterns.PRICE_QUOTED)
                await self.publish_event(
                    domain,
                    event_type,
                    {
                        "order_id": order.get("order_id"),
                        "symbol": symbol,
                        "price": price_data["price"],
                        "bid": price_data["bid"],
                        "ask": price_data["ask"],
                        "timestamp": price_data["timestamp"],
                    },
                )
                self._metrics.increment("events.price_quoted.published")

        # Store reference to get_price for use in price update loop
        self._get_price = get_price

        # Start price update task
        self._price_update_task = asyncio.create_task(self._price_update_loop())

    async def _price_update_loop(self) -> None:
        """Periodically emit price updates."""
        while not self._shutdown_event.is_set():
            try:
                # Emit price updates every 5 seconds
                await asyncio.sleep(5)

                # Pick a random symbol to update
                symbol = random.choice(list(self._base_prices.keys()))  # nosec

                # Get current price by calling the stored get_price method
                price_data = await self._get_price({"symbol": symbol})

                # Emit price update event
                domain, event_type = parse_event_pattern(EventPatterns.PRICE_UPDATED)
                await self.publish_event(
                    domain,
                    event_type,
                    {
                        "symbol": symbol,
                        "price": price_data["price"],
                        "bid": price_data["bid"],
                        "ask": price_data["ask"],
                        "timestamp": price_data["timestamp"],
                    },
                )
                self._metrics.increment("events.price_updated.published")
                self._metrics.record("prices.current", price_data["price"])

            except Exception as e:
                if self._logger:
                    self._logger.error("Price update error", error=str(e))

    async def stop(self) -> None:
        """Stop the service."""
        # Cancel price update task
        if self._price_update_task:
            self._price_update_task.cancel()
            try:
                await self._price_update_task
            except asyncio.CancelledError:
                pass

        # Call parent stop
        await super().stop()
