"""Domain models for Order Service."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OrderSide(str, Enum):
    """Order side enumeration."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """Order status enumeration."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"


class RiskLevel(str, Enum):
    """Risk level enumeration."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Order(BaseModel):
    """Order domain model with strict validation."""

    model_config = ConfigDict(
        strict=True,
        validate_assignment=True,
        arbitrary_types_allowed=False,
        extra="forbid",  # Reject extra fields
    )

    order_id: str = Field(..., description="Unique order identifier", pattern=r"^ORD-\d{6}$")
    symbol: str = Field(..., description="Trading symbol", min_length=1, max_length=10)
    quantity: float = Field(..., gt=0, le=1_000_000, description="Order quantity")
    side: OrderSide = Field(..., description="Order side (BUY/SELL)")
    order_type: OrderType = Field(OrderType.MARKET, description="Order type")
    status: OrderStatus = Field(OrderStatus.PENDING, description="Order status")
    created_at: datetime = Field(..., description="Order creation timestamp")
    instance_id: str = Field(..., description="Service instance that created the order")
    price: float | None = Field(
        None, gt=0, le=1_000_000, description="Order price (for limit orders)"
    )
    filled_quantity: float = Field(0, ge=0, description="Filled quantity")
    risk_level: RiskLevel | None = Field(None, description="Risk assessment level")
    risk_assessed_at: datetime | None = Field(None, description="Risk assessment timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional order metadata")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format."""
        return v.upper().strip()

    @field_validator("filled_quantity")
    @classmethod
    def validate_filled_quantity(cls, v: float, info) -> float:
        """Validate filled quantity doesn't exceed order quantity."""
        if "quantity" in info.data and v > info.data["quantity"]:
            raise ValueError("Filled quantity cannot exceed order quantity")
        return v

    @field_validator("price")
    @classmethod
    def validate_price_for_limit_orders(cls, v: float | None, info) -> float | None:
        """Validate price is required for limit orders."""
        if "order_type" in info.data:
            order_type = info.data["order_type"]
            if order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and v is None:
                raise ValueError(f"Price is required for {order_type.value} orders")
        return v

    @model_validator(mode="after")
    def validate_order_consistency(self) -> Order:
        """Validate order consistency after all fields are set."""
        # Check price requirement for limit orders
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and self.price is None:
            raise ValueError(f"Price is required for {self.order_type.value} orders")
        return self
