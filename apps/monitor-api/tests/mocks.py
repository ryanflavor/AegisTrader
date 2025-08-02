"""Mock implementations for testing.

This module provides mock implementations of ports and adapters
for use in unit and integration tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

from app.domain.models import ServiceDefinition
from app.ports.kv_store import KVStorePort

if TYPE_CHECKING:
    from collections.abc import Callable


class MockKVStore(KVStorePort):
    """Mock implementation of KVStorePort for testing."""

    def __init__(self):
        """Initialize the mock KV store."""
        self.store: dict[str, tuple[ServiceDefinition, int]] = {}
        self.revision_counter = 0
        self.get = AsyncMock(side_effect=self._get)
        self.put = AsyncMock(side_effect=self._put)
        self.update = AsyncMock(side_effect=self._update)
        self.delete = AsyncMock(side_effect=self._delete)
        self.list_all = AsyncMock(side_effect=self._list_all)

    async def _get(self, key: str) -> ServiceDefinition | None:
        """Mock get implementation."""
        entry = self.store.get(key)
        return entry[0] if entry else None

    async def _put(self, key: str, value: ServiceDefinition) -> None:
        """Mock put implementation."""
        from app.domain.exceptions import ServiceAlreadyExistsException

        if key in self.store:
            raise ServiceAlreadyExistsException(key)
        self.revision_counter += 1
        self.store[key] = (value, self.revision_counter)

    async def _update(
        self, key: str, value: ServiceDefinition, revision: int | None = None
    ) -> None:
        """Mock update implementation."""
        from app.domain.exceptions import (
            ConcurrentUpdateException,
            ServiceNotFoundException,
        )

        if key not in self.store:
            raise ServiceNotFoundException(key)

        current_value, current_revision = self.store[key]
        if revision is not None and revision != current_revision:
            raise ConcurrentUpdateException(key)

        self.revision_counter += 1
        self.store[key] = (value, self.revision_counter)

    async def _delete(self, key: str) -> None:
        """Mock delete implementation."""
        from app.domain.exceptions import ServiceNotFoundException

        if key not in self.store:
            raise ServiceNotFoundException(key)
        del self.store[key]

    async def _list_all(self) -> list[ServiceDefinition]:
        """Mock list_all implementation."""
        return [entry[0] for entry in self.store.values()]

    async def get_with_revision(self, key: str) -> tuple[ServiceDefinition | None, int | None]:
        """Get with revision for testing."""
        entry = self.store.get(key)
        if entry:
            return entry
        return None, None


def create_mock_connection_manager(kv_store: KVStorePort | None = None) -> Mock:
    """Create a mock connection manager for testing.

    Args:
        kv_store: Optional KV store instance to use

    Returns:
        Mock connection manager
    """
    mock = Mock()
    mock.kv_store = kv_store or MockKVStore()
    mock.startup = AsyncMock()
    mock.shutdown = AsyncMock()
    return mock


def override_dependencies(overrides: dict[str, Callable]) -> None:
    """Override FastAPI dependencies for testing.

    Args:
        overrides: Dictionary of dependency function names to override functions
    """
    from app.infrastructure.api import dependencies

    for name, override in overrides.items():
        setattr(dependencies, name, override)
