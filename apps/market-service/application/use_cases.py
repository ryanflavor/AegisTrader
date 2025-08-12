"""
Application Use Cases for Market Service.

These use cases orchestrate domain logic and coordinate
between different domain objects and infrastructure services.
They represent the application's business workflows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domain.market_data import (
    InstrumentType,
    MarketDataGateway,
    Price,
    Symbol,
    Tick,
    TimeRange,
    Volume,
)
from domain.ports import (
    EventPublisher,
    MarketDataGatewayRepository,
    MarketDataSource,
    TickDataRepository,
)

# DTOs for Use Cases


class ConnectGatewayRequest(BaseModel):
    """Request to connect a market data gateway."""

    model_config = ConfigDict(strict=True)

    gateway_id: str
    gateway_type: str
    connection_params: dict[str, str] = Field(default_factory=dict)
    max_subscriptions: Annotated[int, Field(gt=0)] = 100


class ConnectGatewayResponse(BaseModel):
    """Response from connecting a gateway."""

    model_config = ConfigDict(strict=True)

    success: bool
    gateway_uuid: UUID
    session_id: UUID | None = None
    message: str


class SubscribeMarketDataRequest(BaseModel):
    """Request to subscribe to market data."""

    model_config = ConfigDict(strict=True)

    gateway_id: str
    symbol: str
    exchange: str
    subscriber_id: str
    instrument_type: InstrumentType = InstrumentType.STOCK


class SubscribeMarketDataResponse(BaseModel):
    """Response from subscribing to market data."""

    model_config = ConfigDict(strict=True)

    success: bool
    subscription_id: UUID | None = None
    message: str


class ProcessTickRequest(BaseModel):
    """Request to process a market tick."""

    model_config = ConfigDict(strict=True)

    gateway_id: str
    symbol: str
    exchange: str
    price: Annotated[float, Field(ge=0)]
    volume: Annotated[int, Field(ge=0)]
    timestamp: datetime
    sequence_number: Annotated[int, Field(ge=0)]

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if v.tzinfo is None:
            # Assume UTC if no timezone
            return v.replace(tzinfo=UTC)
        return v


class GetMarketDataRequest(BaseModel):
    """Request to retrieve market data."""

    model_config = ConfigDict(strict=True)

    symbol: str
    exchange: str
    start_time: datetime
    end_time: datetime
    limit: Annotated[int, Field(gt=0, le=10000)] | None = 1000

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        """Ensure timestamps are timezone-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class GetMarketDataResponse(BaseModel):
    """Response with market data."""

    model_config = ConfigDict(strict=True)

    ticks: list[dict]
    count: int
    symbol: str
    exchange: str


# Use Case Implementations


class ConnectGatewayUseCase:
    """Use case for connecting a market data gateway."""

    def __init__(
        self,
        gateway_repo: MarketDataGatewayRepository,
        market_source: MarketDataSource,
        event_publisher: EventPublisher,
    ):
        """Initialize use case with dependencies."""
        self.gateway_repo = gateway_repo
        self.market_source = market_source
        self.event_publisher = event_publisher

    async def execute(self, request: ConnectGatewayRequest) -> ConnectGatewayResponse:
        """
        Connect a market data gateway.

        Steps:
        1. Check if gateway already exists
        2. Create new gateway or retrieve existing
        3. Connect to market source
        4. Connect gateway (creates session)
        5. Save gateway state
        6. Publish domain events
        """
        try:
            # Check if gateway exists
            gateway = await self.gateway_repo.get(request.gateway_id)

            if gateway is None:
                # Create new gateway
                gateway = MarketDataGateway(
                    gateway_id=request.gateway_id,
                    gateway_type=request.gateway_type,
                    max_subscriptions=request.max_subscriptions,
                )
            elif gateway.is_connected:
                return ConnectGatewayResponse(
                    success=False,
                    gateway_uuid=gateway.id,
                    session_id=gateway.current_session.id if gateway.current_session else None,
                    message=f"Gateway {request.gateway_id} is already connected",
                )

            # Connect to market source
            await self.market_source.connect(request.connection_params)

            # Connect gateway (creates session)
            gateway.connect(request.connection_params)

            # Save gateway state
            await self.gateway_repo.save(gateway)

            # Publish domain events
            events = gateway.collect_events()
            await self.event_publisher.publish_batch(events)

            return ConnectGatewayResponse(
                success=True,
                gateway_uuid=gateway.id,
                session_id=gateway.current_session.id if gateway.current_session else None,
                message=f"Gateway {request.gateway_id} connected successfully",
            )

        except Exception as e:
            return ConnectGatewayResponse(
                success=False,
                gateway_uuid=UUID("00000000-0000-0000-0000-000000000000"),
                message=f"Failed to connect gateway: {str(e)}",
            )


class DisconnectGatewayUseCase:
    """Use case for disconnecting a market data gateway."""

    def __init__(
        self,
        gateway_repo: MarketDataGatewayRepository,
        market_source: MarketDataSource,
        event_publisher: EventPublisher,
    ):
        """Initialize use case with dependencies."""
        self.gateway_repo = gateway_repo
        self.market_source = market_source
        self.event_publisher = event_publisher

    async def execute(self, gateway_id: str, reason: str = "Manual disconnect") -> bool:
        """
        Disconnect a market data gateway.

        Steps:
        1. Retrieve gateway
        2. Disconnect gateway (ends session)
        3. Disconnect from market source
        4. Save gateway state
        5. Publish domain events
        """
        gateway = await self.gateway_repo.get(gateway_id)

        if gateway is None:
            raise ValueError(f"Gateway {gateway_id} not found")

        if not gateway.is_connected:
            return False

        # Disconnect gateway
        gateway.disconnect(reason)

        # Disconnect from market source
        await self.market_source.disconnect()

        # Save gateway state
        await self.gateway_repo.save(gateway)

        # Publish domain events
        events = gateway.collect_events()
        await self.event_publisher.publish_batch(events)

        return True


class SubscribeMarketDataUseCase:
    """Use case for subscribing to market data."""

    def __init__(
        self,
        gateway_repo: MarketDataGatewayRepository,
        market_source: MarketDataSource,
        event_publisher: EventPublisher,
    ):
        """Initialize use case with dependencies."""
        self.gateway_repo = gateway_repo
        self.market_source = market_source
        self.event_publisher = event_publisher

    async def execute(self, request: SubscribeMarketDataRequest) -> SubscribeMarketDataResponse:
        """
        Subscribe to market data for a symbol.

        Steps:
        1. Retrieve gateway
        2. Create subscription through gateway
        3. Subscribe through market source
        4. Save gateway state
        5. Publish domain events
        """
        try:
            gateway = await self.gateway_repo.get(request.gateway_id)

            if gateway is None:
                return SubscribeMarketDataResponse(
                    success=False,
                    message=f"Gateway {request.gateway_id} not found",
                )

            if not gateway.is_connected:
                return SubscribeMarketDataResponse(
                    success=False,
                    message=f"Gateway {request.gateway_id} is not connected",
                )

            # Create symbol value object
            symbol = Symbol(value=request.symbol, exchange=request.exchange)

            # Subscribe through gateway
            subscription = gateway.subscribe(
                symbol=symbol,
                subscriber_id=request.subscriber_id,
                instrument_type=request.instrument_type,
            )

            # Subscribe through market source
            await self.market_source.subscribe(symbol)

            # Save gateway state
            await self.gateway_repo.save(gateway)

            # Publish domain events
            events = gateway.collect_events()
            await self.event_publisher.publish_batch(events)

            return SubscribeMarketDataResponse(
                success=True,
                subscription_id=subscription.id,
                message=f"Subscribed to {symbol}",
            )

        except Exception as e:
            return SubscribeMarketDataResponse(
                success=False,
                message=f"Failed to subscribe: {str(e)}",
            )


class ProcessTickUseCase:
    """Use case for processing market ticks."""

    def __init__(
        self,
        gateway_repo: MarketDataGatewayRepository,
        tick_repo: TickDataRepository,
        event_publisher: EventPublisher,
    ):
        """Initialize use case with dependencies."""
        self.gateway_repo = gateway_repo
        self.tick_repo = tick_repo
        self.event_publisher = event_publisher

    async def execute(self, request: ProcessTickRequest) -> bool:
        """
        Process an incoming market tick.

        Steps:
        1. Retrieve gateway
        2. Create tick value object
        3. Process tick through gateway
        4. Save tick to repository
        5. Save gateway state
        6. Publish domain events
        """
        gateway = await self.gateway_repo.get(request.gateway_id)

        if gateway is None or not gateway.is_connected:
            return False

        # Create tick value object
        tick = Tick(
            symbol=Symbol(value=request.symbol, exchange=request.exchange),
            price=Price(value=request.price),
            volume=Volume(value=request.volume),
            timestamp=request.timestamp,
            sequence_number=request.sequence_number,
        )

        try:
            # Process tick through gateway
            gateway.process_tick(tick)

            # Save tick to repository
            await self.tick_repo.save_tick(tick)

            # Update heartbeat
            gateway.update_heartbeat()

            # Save gateway state
            await self.gateway_repo.save(gateway)

            # Publish domain events
            events = gateway.collect_events()
            await self.event_publisher.publish_batch(events)

            return True

        except Exception:
            return False


class GetMarketDataUseCase:
    """Use case for retrieving historical market data."""

    def __init__(self, tick_repo: TickDataRepository):
        """Initialize use case with dependencies."""
        self.tick_repo = tick_repo

    async def execute(self, request: GetMarketDataRequest) -> GetMarketDataResponse:
        """
        Retrieve historical market data.

        Steps:
        1. Create value objects from request
        2. Query tick repository
        3. Transform ticks to response format
        """
        # Create value objects
        symbol = Symbol(value=request.symbol, exchange=request.exchange)
        time_range = TimeRange(start=request.start_time, end=request.end_time)

        # Query repository
        ticks = await self.tick_repo.get_ticks(
            symbol=symbol,
            time_range=time_range,
            limit=request.limit,
        )

        # Transform to response format
        tick_dicts = [
            {
                "symbol": str(tick.symbol),
                "price": float(tick.price.value),
                "volume": tick.volume.value,
                "timestamp": tick.timestamp.isoformat(),
                "sequence_number": tick.sequence_number,
            }
            for tick in ticks
        ]

        return GetMarketDataResponse(
            ticks=tick_dicts,
            count=len(tick_dicts),
            symbol=request.symbol,
            exchange=request.exchange,
        )
