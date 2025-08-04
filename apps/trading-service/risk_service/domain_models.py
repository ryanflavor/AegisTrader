"""Domain models for Risk Service."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk level enumeration."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskAssessment(BaseModel):
    """Risk assessment domain model."""

    order_id: str | None = Field(None, description="Associated order ID")
    symbol: str = Field(..., description="Trading symbol")
    risk_level: RiskLevel = Field(..., description="Assessed risk level")
    risk_score: float = Field(..., ge=0, le=100, description="Risk score (0-100)")
    risk_factors: list[str] = Field(default_factory=list, description="Identified risk factors")
    position_limit: float = Field(..., gt=0, description="Position limit for the symbol")
    current_position: float = Field(..., description="Current position")
    new_position: float = Field(..., description="New position after order")
    assessment_time: datetime = Field(..., description="Assessment timestamp")
    instance_id: str = Field(..., description="Service instance that performed assessment")


class Position(BaseModel):
    """Position domain model."""

    symbol: str = Field(..., description="Trading symbol")
    position: float = Field(
        ..., description="Current position (positive for long, negative for short)"
    )
    timestamp: datetime = Field(..., description="Position update timestamp")
    instance_id: str | None = Field(None, description="Service instance managing the position")
