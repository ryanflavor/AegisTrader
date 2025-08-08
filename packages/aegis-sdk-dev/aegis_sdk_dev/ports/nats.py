"""NATS connection port for messaging operations."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class NATSConnectionPort(Protocol):
    """Port for NATS connection operations."""

    async def connect(self, url: str, timeout: float = 5.0) -> bool:
        """Connect to NATS server.

        Args:
            url: NATS server URL
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully

        Raises:
            ConnectionError: If unable to connect
        """
        ...

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        ...

    async def is_connected(self) -> bool:
        """Check if connected to NATS.

        Returns:
            True if connected, False otherwise
        """
        ...

    async def get_server_info(self) -> dict[str, Any]:
        """Get NATS server information.

        Returns:
            Server information dictionary

        Raises:
            ConnectionError: If not connected
        """
        ...

    async def create_kv_bucket(self, bucket: str) -> bool:
        """Create a KV bucket.

        Args:
            bucket: Bucket name

        Returns:
            True if created successfully

        Raises:
            ConnectionError: If not connected
        """
        ...

    async def bucket_exists(self, bucket: str) -> bool:
        """Check if a KV bucket exists.

        Args:
            bucket: Bucket name

        Returns:
            True if bucket exists, False otherwise

        Raises:
            ConnectionError: If not connected
        """
        ...
