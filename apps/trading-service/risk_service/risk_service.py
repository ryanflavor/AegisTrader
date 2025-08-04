"""Risk Service implementation using AegisSDK."""

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


class RiskService(Service):
    """Example risk assessment service."""

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
        """Initialize risk service."""
        super().__init__(
            service_name=ServiceNames.RISK_SERVICE,
            message_bus=message_bus,
            instance_id=instance_id,
            version=version,
            service_registry=service_registry,
            service_discovery=service_discovery,
            logger=logger,
        )

        # Risk thresholds
        self._position_limits = {
            "AAPL": 10000,
            "GOOGL": 5000,
            "MSFT": 8000,
            "AMZN": 6000,
            "TSLA": 3000,
            "BTC": 1000,
            "ETH": 2000,
        }

        # Track current positions (simplified)
        self._positions: dict[str, float] = {}
        self._daily_volume: dict[str, float] = {}

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
            self._metrics.gauge("risk.monitored_symbols", len(self._position_limits))
            self._metrics.gauge("risk.active_positions", len(self._positions))
            return {
                "status": "healthy",
                "service": self.service_name,
                "instance": self.instance_id,
                "uptime": (
                    (datetime.now(UTC) - self._start_time).total_seconds()
                    if self._start_time
                    else 0
                ),
                "monitored_symbols": len(self._position_limits),
                "active_positions": len(self._positions),
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

        @self.rpc("assess_risk")
        async def assess_risk(params: dict[str, Any]) -> dict[str, Any]:
            """Assess risk for an order."""
            with self._metrics.timer("rpc.assess_risk.duration_ms"):
                self._metrics.increment("risk.assessments")
                order_id = params.get("order_id")
                symbol = params.get("symbol")
                quantity = params.get("quantity", 0)
                side = params.get("side", "BUY")

            if not symbol:
                raise ValueError("symbol is required")

            # Simulate risk calculation
            risk_factors = []
            risk_score = 0

            # Check position limits
            position_limit = self._position_limits.get(symbol, 5000)
            current_position = self._positions.get(symbol, 0)

            if side == "BUY":
                new_position = current_position + quantity
            else:
                new_position = current_position - quantity

            if abs(new_position) > position_limit:
                risk_factors.append("POSITION_LIMIT_EXCEEDED")
                risk_score += 50

            # Check daily volume
            daily_volume = self._daily_volume.get(symbol, 0)
            if daily_volume + quantity > position_limit * 2:
                risk_factors.append("HIGH_DAILY_VOLUME")
                risk_score += 30

            # Random market risk factor
            market_risk = random.uniform(0, 30)  # nosec
            risk_score += market_risk
            if market_risk > 20:
                risk_factors.append("HIGH_MARKET_VOLATILITY")

            # Determine risk level
            if risk_score >= 70:
                risk_level = "HIGH"
            elif risk_score >= 40:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            self._metrics.increment(f"risk.level.{risk_level.lower()}")
            self._metrics.record("risk.score", risk_score)

            return {
                "order_id": order_id,
                "symbol": symbol,
                "risk_level": risk_level,
                "risk_score": round(risk_score, 2),
                "risk_factors": risk_factors,
                "position_limit": position_limit,
                "current_position": current_position,
                "new_position": new_position,
                "assessment_time": datetime.now(UTC).isoformat(),
                "instance": self.instance_id,
            }

        @self.rpc("get_positions")
        async def get_positions(params: dict[str, Any]) -> dict[str, Any]:
            """Get current positions."""
            return {
                "positions": self._positions,
                "daily_volumes": self._daily_volume,
                "limits": self._position_limits,
                "timestamp": datetime.now(UTC).isoformat(),
                "instance": self.instance_id,
            }

        @self.rpc("update_limits")
        async def update_limits(params: dict[str, Any]) -> dict[str, Any]:
            """Update position limits."""
            symbol = params.get("symbol")
            limit = params.get("limit")

            if not symbol or limit is None:
                raise ValueError("symbol and limit are required")

            self._position_limits[symbol] = limit

            return {
                "symbol": symbol,
                "new_limit": limit,
                "message": "Position limit updated",
                "instance": self.instance_id,
            }

        # Subscribe to order events
        @self.subscribe(EventPatterns.ORDER_CREATED)
        async def handle_order_created(event: Event) -> None:
            """Assess risk for new orders."""
            order = event.payload.get("order", {})

            # Assess risk
            risk_assessment = await assess_risk(
                {
                    "order_id": order.get("order_id"),
                    "symbol": order.get("symbol"),
                    "quantity": order.get("quantity", 0),
                    "side": order.get("side", "BUY"),
                }
            )

            # Emit risk assessment event
            domain, event_type = parse_event_pattern(EventPatterns.RISK_ASSESSED)
            await self.publish_event(domain, event_type, risk_assessment)
            self._metrics.increment("events.risk_assessed.published")

            # Update positions if risk is acceptable
            if risk_assessment["risk_level"] != "HIGH":
                symbol = order.get("symbol")
                quantity = order.get("quantity", 0)
                side = order.get("side", "BUY")

                if symbol:
                    current = self._positions.get(symbol, 0)
                    if side == "BUY":
                        self._positions[symbol] = current + quantity
                    else:
                        self._positions[symbol] = current - quantity

                    # Update daily volume
                    self._daily_volume[symbol] = self._daily_volume.get(symbol, 0) + quantity

        @self.subscribe(EventPatterns.ORDER_FILLED)
        async def handle_order_filled(event: Event) -> None:
            """Update positions for filled orders."""
            order = event.payload.get("order", {})
            symbol = order.get("symbol")
            quantity = order.get("filled_quantity", order.get("quantity", 0))
            side = order.get("side", "BUY")

            if symbol and quantity:
                current = self._positions.get(symbol, 0)
                if side == "BUY":
                    self._positions[symbol] = current + quantity
                else:
                    self._positions[symbol] = current - quantity

                # Emit position update event
                domain, event_type = parse_event_pattern(EventPatterns.POSITION_UPDATED)
                await self.publish_event(
                    domain,
                    event_type,
                    {
                        "symbol": symbol,
                        "position": self._positions[symbol],
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
                self._metrics.increment("events.position_updated.published")
                self._metrics.gauge(f"positions.{symbol}", self._positions[symbol])
