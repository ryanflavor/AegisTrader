"""
Base repository classes following DDD patterns.

This module provides abstract base classes for repository implementations,
ensuring consistent behavior and reducing code duplication.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

# Type variable for aggregate root
T = TypeVar("T")


class RepositoryConfig(BaseModel):
    """Base configuration for all repositories."""

    model_config = ConfigDict(strict=True, frozen=True)

    enable_caching: bool = False
    cache_ttl_seconds: int = 300
    max_cache_size: int = 1000


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository following DDD patterns.

    This base class provides common functionality for all repositories
    and ensures they follow the repository pattern correctly.
    """

    def __init__(self, config: RepositoryConfig | None = None):
        """Initialize repository with optional configuration."""
        self.config = config or RepositoryConfig()
        self._cache: dict[str, T] = {} if self.config.enable_caching else {}

    @abstractmethod
    async def save(self, aggregate: T) -> None:
        """
        Persist an aggregate root.

        Args:
            aggregate: The aggregate root to persist
        """
        pass

    @abstractmethod
    async def get(self, id: str) -> T | None:
        """
        Retrieve an aggregate by ID.

        Args:
            id: The unique identifier

        Returns:
            The aggregate if found, None otherwise
        """
        pass

    @abstractmethod
    async def exists(self, id: str) -> bool:
        """
        Check if an aggregate exists.

        Args:
            id: The unique identifier

        Returns:
            True if exists, False otherwise
        """
        pass

    def _get_from_cache(self, key: str) -> T | None:
        """Get item from cache if enabled."""
        if self.config.enable_caching:
            return self._cache.get(key)
        return None

    def _add_to_cache(self, key: str, value: T) -> None:
        """Add item to cache if enabled."""
        if self.config.enable_caching:
            # Simple LRU-like behavior
            if len(self._cache) >= self.config.max_cache_size:
                # Remove oldest item (first in dict)
                first_key = next(iter(self._cache))
                del self._cache[first_key]
            self._cache[key] = value

    def _clear_cache(self) -> None:
        """Clear the cache."""
        if self.config.enable_caching:
            self._cache.clear()


class BaseEventStore(ABC):
    """
    Abstract base class for event stores.

    Follows Event Sourcing pattern for domain event persistence.
    """

    @abstractmethod
    async def append_events(self, aggregate_id: str, events: list) -> None:
        """
        Append events to the event stream.

        Args:
            aggregate_id: The aggregate identifier
            events: List of domain events to append
        """
        pass

    @abstractmethod
    async def get_events(
        self,
        aggregate_id: str,
        from_version: int | None = None,
    ) -> list:
        """
        Retrieve events for an aggregate.

        Args:
            aggregate_id: The aggregate identifier
            from_version: Optional starting version

        Returns:
            List of events for the aggregate
        """
        pass
