"""Order Service implementation using AegisSDK."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from aegis_sdk.application import Service
from aegis_sdk.domain.models import Event
from aegis_sdk.ports.logger import LoggerPort
from aegis_sdk.ports.message_bus import MessageBusPort
from aegis_sdk.ports.metrics import MetricsPort
from aegis_sdk.ports.service_discovery import ServiceDiscoveryPort
from aegis_sdk.ports.service_registry import ServiceRegistryPort
from pydantic import ValidationError
from shared_contracts import EventPatterns, RPCPatterns, ServiceNames, parse_event_pattern

from .domain_models import Order, OrderSide, OrderStatus, OrderType, RiskLevel
from .ports import OrderRepositoryPort, PricingServicePort
from .repositories import InMemoryOrderRepository


class OrderService(Service):
    """Order management service with hexagonal architecture."""

    def __init__(
        self,
        message_bus: MessageBusPort,
        instance_id: str | None = None,
        version: str = "1.0.0",
        service_registry: ServiceRegistryPort | None = None,
        service_discovery: ServiceDiscoveryPort | None = None,
        logger: LoggerPort | None = None,
        metrics: MetricsPort | None = None,
        order_repository: OrderRepositoryPort | None = None,
        pricing_service: PricingServicePort | None = None,
    ):
        """Initialize order service."""
        super().__init__(
            service_name=ServiceNames.ORDER_SERVICE,
            message_bus=message_bus,
            instance_id=instance_id,
            version=version,
            service_registry=service_registry,
            service_discovery=service_discovery,
            logger=logger,
        )

        # Domain dependencies
        self._order_repository = order_repository or InMemoryOrderRepository()
        self._pricing_service = pricing_service

        # Infrastructure
        self._metrics = metrics

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
            order_count = await self._order_repository.count()
            self._metrics.gauge("orders.active", order_count)
            return {
                "status": "healthy",
                "service": self.service_name,
                "instance": self.instance_id,
                "uptime": (
                    (datetime.now(UTC) - self._start_time).total_seconds()
                    if self._start_time
                    else 0
                ),
                "order_count": await self._order_repository.count(),
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

        @self.rpc("create_order")
        async def create_order(params: dict[str, Any]) -> dict[str, Any]:
            """Create a new order."""
            timer_context = (
                self._metrics.timer("rpc.create_order.duration_ms") if self._metrics else None
            )

            try:
                if timer_context:
                    timer_context.__enter__()

                # Validate input parameters using Pydantic
                try:
                    order = Order(
                        order_id=await self._order_repository.get_next_order_id(),
                        symbol=params.get("symbol", "UNKNOWN"),
                        quantity=params.get("quantity", 0),
                        side=OrderSide(params.get("side", "BUY")),
                        order_type=OrderType(params.get("order_type", "MARKET")),
                        status=OrderStatus.PENDING,
                        created_at=datetime.now(UTC),
                        instance_id=self.instance_id,
                    )
                except ValidationError as e:
                    return {"error": "Invalid order parameters", "details": e.errors()}

                # Save order to repository
                await self._order_repository.save(order)

                if self._metrics:
                    self._metrics.increment("orders.created")

                # Log order creation
                if self._logger:
                    self._logger.info(
                        f"🎯 Created order: {order.order_id} - Symbol: {order.symbol}, "
                        f"Quantity: {order.quantity}, Side: {order.side.value}"
                    )

                # Emit order created event
                domain, event_type = parse_event_pattern(EventPatterns.ORDER_CREATED)
                await self.publish_event(
                    domain,
                    event_type,
                    {
                        "order_id": order.order_id,
                        "symbol": order.symbol,
                        "quantity": order.quantity,
                        "side": order.side.value,
                        "order_type": order.order_type.value,
                        "status": order.status.value,
                        "created_at": order.created_at.isoformat(),
                        "instance_id": order.instance_id,
                    },
                )
                if self._metrics:
                    self._metrics.increment("events.order_created.published")

                # Get price from pricing service
                if self._pricing_service:
                    try:
                        price = await self._pricing_service.get_price(order.symbol)
                        order.price = price
                        await self._order_repository.save(order)
                    except Exception as e:
                        if self._metrics:
                            self._metrics.increment("rpc.pricing_service.failures")
                        if self._logger:
                            self._logger.warning("Failed to get price", error=str(e))
                        # Use default price if pricing service is unavailable
                        order.price = 100.0
                        await self._order_repository.save(order)
                elif self._discovery:
                    # Fallback to direct RPC call if no pricing service port
                    try:
                        price_info = await self.call_rpc(
                            ServiceNames.PRICING_SERVICE, "get_price", {"symbol": order.symbol}
                        )
                        order.price = price_info.get("price", 0)
                        await self._order_repository.save(order)
                    except Exception as e:
                        if self._metrics:
                            self._metrics.increment("rpc.pricing_service.failures")
                        if self._logger:
                            self._logger.warning("Failed to get price", error=str(e))
                        order.price = 100.0
                        await self._order_repository.save(order)

                return {"order": order.model_dump()}

            finally:
                if timer_context:
                    timer_context.__exit__(None, None, None)

        @self.rpc("get_order")
        async def get_order(params: dict[str, Any]) -> dict[str, Any]:
            """Get order by ID."""
            order_id = params.get("order_id")
            if not order_id:
                return {"error": "order_id is required"}

            order = await self._order_repository.get(order_id)
            if not order:
                return {"error": f"Order not found: {order_id}"}

            return {"order": order.model_dump()}

        @self.rpc("list_orders")
        async def list_orders(params: dict[str, Any]) -> dict[str, Any]:
            """List all orders."""
            limit = params.get("limit", 100)
            orders = await self._order_repository.list(limit=limit)
            total = await self._order_repository.count()

            return {
                "orders": [order.model_dump() for order in orders],
                "total": total,
                "instance": self.instance_id,
            }

        # Subscribe to risk events
        @self.subscribe(EventPatterns.RISK_EVENTS)
        async def handle_risk_event(event: Event) -> None:
            """Handle risk assessment events."""
            if event.domain == "risk" and event.event_type == "assessed":
                order_id = event.payload.get("order_id")
                risk_level_str = event.payload.get("risk_level")

                if not order_id or not risk_level_str:
                    return

                order = await self._order_repository.get(order_id)
                if order:
                    try:
                        # Update order with risk assessment
                        order.risk_level = RiskLevel(risk_level_str)
                        order.risk_assessed_at = datetime.now(UTC)

                        # Update order status based on risk
                        previous_status = order.status
                        if order.risk_level == RiskLevel.HIGH:
                            order.status = OrderStatus.REJECTED
                        else:
                            order.status = OrderStatus.APPROVED

                        # Save updated order
                        await self._order_repository.save(order)

                        # Emit order updated event
                        domain, event_type = parse_event_pattern(EventPatterns.ORDER_UPDATED)
                        await self.publish_event(
                            domain,
                            event_type,
                            {
                                "order_id": order_id,
                                "symbol": order.symbol,
                                "status": order.status.value,
                                "risk_level": order.risk_level.value,
                                "risk_assessed_at": order.risk_assessed_at.isoformat(),
                                "previous_status": previous_status.value,
                                "update_reason": "Risk assessment completed",
                            },
                        )

                        if self._metrics:
                            self._metrics.increment("events.order_updated.published")
                            self._metrics.increment(
                                f"orders.risk_assessment.{risk_level_str.lower()}"
                            )

                    except (ValidationError, ValueError) as e:
                        if self._logger:
                            self._logger.error(
                                f"Invalid risk level: {risk_level_str}", error=str(e)
                            )
