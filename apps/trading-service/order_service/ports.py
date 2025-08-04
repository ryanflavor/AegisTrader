"""Ports (interfaces) for Order Service following hexagonal architecture."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from .domain_models import Order


class OrderRepositoryPort(ABC):
    """Port for order persistence operations."""

    @abstractmethod
    async def save(self, order: Order) -> None:
        """Save or update an order."""

    @abstractmethod
    async def get(self, order_id: str) -> Order | None:
        """Get an order by ID."""

    @abstractmethod
    async def list(self, limit: int = 100) -> list[Order]:
        """List orders with optional limit."""

    @abstractmethod
    async def count(self) -> int:
        """Count total orders."""

    @abstractmethod
    async def get_next_order_id(self) -> str:
        """Generate the next order ID."""


class PricingServicePort(Protocol):
    """Port for pricing service operations."""

    async def get_price(self, symbol: str) -> float:
        """Get current price for a symbol."""


class RiskAssessmentPort(Protocol):
    """Port for risk assessment operations."""

    async def assess_order_risk(self, order: Order) -> tuple[str, float]:
        """Assess risk for an order, returns (risk_level, risk_score)."""
