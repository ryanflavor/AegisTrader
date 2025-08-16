"""
Shared value objects used across domain contexts.

These immutable value objects represent core concepts that are
shared between different bounded contexts within the market service.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Symbol:
    """Immutable symbol representation."""

    value: str
    exchange: str

    def __str__(self) -> str:
        """String representation."""
        return f"{self.value}@{self.exchange}"


@dataclass(frozen=True)
class Price:
    """Immutable price value object."""

    value: Decimal

    def __post_init__(self):
        """Validate price."""
        if self.value < 0:
            raise ValueError("Price cannot be negative")


@dataclass(frozen=True)
class Volume:
    """Immutable volume value object."""

    value: int

    def __post_init__(self):
        """Validate volume."""
        if self.value < 0:
            raise ValueError("Volume cannot be negative")


@dataclass(frozen=True)
class Exchange:
    """Immutable exchange identifier."""

    code: str
    name: str = ""

    def __str__(self) -> str:
        """String representation."""
        return self.code
