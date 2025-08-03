"""Connection manager for infrastructure resources.

This module manages the lifecycle of infrastructure connections,
providing a clean separation between connection management and business logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..domain.exceptions import KVStoreException
from ..ports.service_registry_kv_store import ServiceRegistryKVStorePort

if TYPE_CHECKING:
    from ..domain.models import ServiceConfiguration

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages infrastructure connections lifecycle."""

    def __init__(self, config: ServiceConfiguration):
        """Initialize the connection manager.

        Args:
            config: Service configuration
        """
        self.config = config
        self._kv_store: ServiceRegistryKVStorePort | None = None

    async def startup(self) -> None:
        """Initialize all connections during application startup."""
        try:
            # Initialize KV Store connection using AegisSDK
            from .aegis_sdk_kv_adapter import AegisSDKKVAdapter

            self._kv_store = AegisSDKKVAdapter()
            await self._kv_store.connect(self.config.nats_url)
            logger.info("Successfully connected to NATS KV Store")
        except Exception as e:
            logger.error(f"Failed to initialize connections: {e}")
            raise KVStoreException(f"Failed to initialize connections: {e}") from e

    async def shutdown(self) -> None:
        """Clean up all connections during application shutdown."""
        try:
            if self._kv_store and hasattr(self._kv_store, "disconnect"):
                await self._kv_store.disconnect()
                logger.info("Disconnected from NATS KV Store")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    @property
    def kv_store(self) -> ServiceRegistryKVStorePort:
        """Get the KV Store instance.

        Returns:
            ServiceRegistryKVStorePort: The KV Store instance

        Raises:
            KVStoreException: If not initialized
        """
        if not self._kv_store:
            raise KVStoreException("KV Store not initialized. Call startup() first.")
        return self._kv_store


# Global instance managed by the application lifecycle
_connection_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance.

    Returns:
        ConnectionManager: The connection manager instance

    Raises:
        RuntimeError: If not initialized
    """
    if not _connection_manager:
        raise RuntimeError("Connection manager not initialized")
    return _connection_manager


def set_connection_manager(manager: ConnectionManager) -> None:
    """Set the global connection manager instance.

    Args:
        manager: The connection manager to set
    """
    global _connection_manager
    _connection_manager = manager
