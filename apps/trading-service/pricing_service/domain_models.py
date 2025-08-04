"""Domain models for Pricing Service."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Price(BaseModel):
    """Price domain model."""

    symbol: str = Field(..., description="Trading symbol")
    price: float = Field(..., gt=0, description="Current price")
    bid: float = Field(..., gt=0, description="Bid price")
    ask: float = Field(..., gt=0, description="Ask price")
    timestamp: datetime = Field(..., description="Price timestamp")
    instance_id: str | None = Field(None, description="Service instance that provided the price")


class PriceQuote(BaseModel):
    """Price quote for a specific order."""

    order_id: str = Field(..., description="Order ID for which the price was quoted")
    symbol: str = Field(..., description="Trading symbol")
    price: float = Field(..., gt=0, description="Quoted price")
    bid: float = Field(..., gt=0, description="Bid price")
    ask: float = Field(..., gt=0, description="Ask price")
    timestamp: datetime = Field(..., description="Quote timestamp")
    instance_id: str = Field(..., description="Service instance that provided the quote")
