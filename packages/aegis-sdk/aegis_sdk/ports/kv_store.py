"""Key-Value Store interface - Port definition for KV storage infrastructure."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from ..domain.models import KVEntry, KVOptions, KVWatchEvent


class KVStorePort(ABC):
    """Abstract interface for key-value store operations.

    This port defines the contract for key-value storage implementations,
    supporting basic CRUD operations, TTL, and watch capabilities.
    """

    @abstractmethod
    async def connect(self, bucket: str) -> None:
        """Connect to a KV store bucket.

        Args:
            bucket: The name of the KV bucket to connect to
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the KV store."""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to the KV store.

        Returns:
            True if connected, False otherwise
        """
        ...

    # Basic Operations
    @abstractmethod
    async def get(self, key: str) -> KVEntry | None:
        """Get a value by key.

        Args:
            key: The key to retrieve

        Returns:
            KVEntry if found, None otherwise
        """
        ...

    @abstractmethod
    async def put(self, key: str, value: Any, options: KVOptions | None = None) -> int:
        """Put a value with optional TTL and revision check.

        Args:
            key: The key to store
            value: The value to store (will be serialized)
            options: Optional KV options (TTL, revision check)

        Returns:
            The revision number of the stored entry

        Raises:
            ValueError: If revision check fails
        """
        ...

    @abstractmethod
    async def delete(self, key: str, revision: int | None = None) -> bool:
        """Delete a key with optional revision check.

        Args:
            key: The key to delete
            revision: Optional revision for optimistic concurrency

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If revision check fails
        """
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists.

        Args:
            key: The key to check

        Returns:
            True if exists, False otherwise
        """
        ...

    # Batch Operations
    @abstractmethod
    async def keys(self, prefix: str = "") -> list[str]:
        """List all keys with optional prefix filter.

        Args:
            prefix: Optional prefix to filter keys

        Returns:
            List of matching keys
        """
        ...

    @abstractmethod
    async def get_many(self, keys: list[str]) -> dict[str, KVEntry]:
        """Get multiple values by keys.

        Args:
            keys: List of keys to retrieve

        Returns:
            Dictionary mapping keys to their entries (only found keys)
        """
        ...

    @abstractmethod
    async def put_many(
        self, entries: dict[str, Any], options: KVOptions | None = None
    ) -> dict[str, int]:
        """Put multiple key-value pairs.

        Args:
            entries: Dictionary of key-value pairs
            options: Optional KV options applied to all entries

        Returns:
            Dictionary mapping keys to their revision numbers
        """
        ...

    @abstractmethod
    async def delete_many(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple keys.

        Args:
            keys: List of keys to delete

        Returns:
            Dictionary mapping keys to deletion success
        """
        ...

    # Advanced Operations
    @abstractmethod
    async def watch(
        self, key: str | None = None, prefix: str | None = None
    ) -> AsyncIterator[KVWatchEvent]:
        """Watch for changes to a key or prefix.

        Args:
            key: Specific key to watch (mutually exclusive with prefix)
            prefix: Key prefix to watch (mutually exclusive with key)

        Yields:
            KVWatchEvent for each change

        Raises:
            ValueError: If both key and prefix are provided
        """
        ...

    @abstractmethod
    async def history(self, key: str, limit: int = 10) -> list[KVEntry]:
        """Get revision history for a key.

        Args:
            key: The key to get history for
            limit: Maximum number of revisions to return

        Returns:
            List of KVEntry objects, newest first
        """
        ...

    @abstractmethod
    async def purge(self, key: str) -> None:
        """Purge all revisions of a key.

        Args:
            key: The key to purge
        """
        ...

    @abstractmethod
    async def clear(self, prefix: str = "") -> int:
        """Clear all keys with optional prefix filter.

        Args:
            prefix: Optional prefix to filter keys to clear

        Returns:
            Number of keys cleared
        """
        ...

    # Status and Maintenance
    @abstractmethod
    async def status(self) -> dict[str, Any]:
        """Get KV store status information.

        Returns:
            Dictionary with status information (bucket name, size, etc.)
        """
        ...
