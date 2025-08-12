"""Repository interfaces for test-example."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """Base repository interface."""

    @abstractmethod
    async def find_by_id(self, id: str) -> T | None:
        """Find entity by ID."""
        pass

    @abstractmethod
    async def find_all(self) -> list[T]:
        """Find all entities."""
        pass

    @abstractmethod
    async def save(self, entity: T) -> None:
        """Save entity."""
        pass

    @abstractmethod
    async def delete(self, id: str) -> None:
        """Delete entity by ID."""
        pass


class UserRepository(Repository):
    """User repository interface."""

    @abstractmethod
    async def find_by_email(self, email: str) -> object | None:
        """Find user by email."""
        pass
