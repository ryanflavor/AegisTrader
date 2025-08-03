"""AegisSDK KV Store adapter for monitor-api.

This adapter wraps AegisSDK's KV Store to match the monitor-api's needs.
Following hexagonal architecture, this adapter translates between infrastructure
concerns and domain needs without leaking domain exceptions into infrastructure.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from aegis_sdk.domain.models import KVOptions
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore

from ..domain.exceptions import KVStoreException
from ..domain.models import ServiceDefinition
from ..ports.service_registry_kv_store import ServiceRegistryKVStorePort

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AegisSDKKVAdapter(ServiceRegistryKVStorePort):
    """Adapter that wraps AegisSDK's KV Store for monitor-api use.

    This adapter translates between monitor-api's ServiceDefinition model
    and AegisSDK's generic KV Store interface. It follows hexagonal architecture
    by not throwing domain-specific exceptions, instead using generic exceptions
    that the application layer can translate.
    """

    def __init__(self):
        """Initialize the adapter."""
        self._nats_adapter: NATSAdapter | None = None
        self._kv_store: NATSKVStore | None = None
        self._connected = False

    async def connect(self, nats_url: str) -> None:
        """Connect to NATS and initialize KV Store.

        Args:
            nats_url: NATS server URL

        Raises:
            KVStoreException: If connection fails
        """
        try:
            # Initialize NATS adapter
            self._nats_adapter = NATSAdapter(pool_size=1, use_msgpack=False)
            await self._nats_adapter.connect([nats_url])

            # Initialize KV Store
            self._kv_store = NATSKVStore(self._nats_adapter)
            await self._kv_store.connect("service-registry")

            self._connected = True
            logger.info("Connected to NATS KV Store via AegisSDK")

        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise KVStoreException(f"Failed to connect to NATS: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        if self._kv_store:
            await self._kv_store.disconnect()
        if self._nats_adapter:
            await self._nats_adapter.disconnect()
        self._connected = False
        logger.info("Disconnected from NATS")

    def _ensure_connected(self) -> None:
        """Ensure we're connected to NATS."""
        if not self._connected or not self._kv_store:
            raise KVStoreException("Not connected to NATS KV Store")

    async def get(self, key: str) -> ServiceDefinition | None:
        """Retrieve a service definition by key.

        Args:
            key: The service name

        Returns:
            ServiceDefinition if found, None otherwise

        Raises:
            KVStoreException: If the operation fails
        """
        self._ensure_connected()

        try:
            # Get from KV Store
            assert self._kv_store is not None  # Type guard for mypy
            entry = await self._kv_store.get(key)
            if entry and entry.value:
                # Parse the value (which should be a dict)
                if isinstance(entry.value, dict):
                    return ServiceDefinition(**entry.value)
                else:
                    # If it's a string, parse it as JSON
                    data = json.loads(entry.value) if isinstance(entry.value, str) else entry.value
                    return ServiceDefinition(**data)
            return None
        except Exception as e:
            logger.error(f"Failed to get key '{key}': {e}")
            raise KVStoreException(f"Failed to get key '{key}': {e}") from e

    async def put(self, key: str, value: ServiceDefinition) -> None:
        """Store a service definition.

        Args:
            key: The service name
            value: The ServiceDefinition to store

        Raises:
            ValueError: If the key already exists (application layer will translate)
            KVStoreException: If the operation fails
        """
        self._ensure_connected()

        try:
            # Check if already exists
            assert self._kv_store is not None  # Type guard for mypy
            existing = await self._kv_store.exists(key)
            if existing:
                # Infrastructure layer reports generic error
                # Application layer will translate to ServiceAlreadyExistsException
                raise ValueError(f"Key '{key}' already exists")

            # Store as dict with ISO format timestamps
            data = value.to_iso_dict()
            await self._kv_store.put(key, data)
            logger.info(f"Stored service definition: {key}")

        except ValueError:
            # Re-raise ValueError for application layer to handle
            raise
        except Exception as e:
            logger.error(f"Failed to put key '{key}': {e}")
            raise KVStoreException(f"Failed to put key '{key}': {e}") from e

    async def update(self, key: str, value: ServiceDefinition, revision: int | None = None) -> None:
        """Update an existing service definition.

        Args:
            key: The service name
            value: The updated ServiceDefinition
            revision: Optional revision for optimistic locking

        Raises:
            ValueError: If key not found or revision mismatch (application layer will translate)
            KVStoreException: If the operation fails
        """
        self._ensure_connected()

        try:
            # Check if exists
            assert self._kv_store is not None  # Type guard for mypy
            existing = await self._kv_store.get(key)
            if not existing:
                # Infrastructure reports generic error
                # Application layer will translate to ServiceNotFoundException
                raise ValueError(f"Key '{key}' not found")

            # Update with revision check if provided
            data = value.to_iso_dict()
            if revision is not None:
                options = KVOptions(revision=revision)
                await self._kv_store.put(key, data, options)
            else:
                await self._kv_store.put(key, data)

            logger.info(f"Updated service definition: {key}")

        except ValueError as e:
            # Check if it's a revision mismatch
            error_msg = str(e)
            if "Revision mismatch" in error_msg or "revision check failed" in error_msg:
                # Infrastructure reports generic error
                # Application layer will translate to ConcurrentUpdateException
                raise ValueError(f"Revision mismatch for key '{key}'") from e
            # Re-raise other ValueErrors
            raise
        except Exception as e:
            logger.error(f"Failed to update key '{key}': {e}")
            raise KVStoreException(f"Failed to update key '{key}': {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a service definition.

        Args:
            key: The service name

        Raises:
            ValueError: If key not found (application layer will translate)
            KVStoreException: If the operation fails
        """
        self._ensure_connected()

        try:
            # Check if exists
            assert self._kv_store is not None  # Type guard for mypy
            existing = await self._kv_store.exists(key)
            if not existing:
                raise ValueError(f"Key '{key}' not found")

            assert self._kv_store is not None  # Type guard for mypy
            await self._kv_store.delete(key)
            logger.info(f"Deleted service definition: {key}")

        except ValueError:
            # Re-raise ValueError for application layer to handle
            raise
        except Exception as e:
            logger.error(f"Failed to delete key '{key}': {e}")
            raise KVStoreException(f"Failed to delete key '{key}': {e}") from e

    async def list_all(self) -> list[ServiceDefinition]:
        """List all service definitions.

        Returns:
            List of all ServiceDefinitions

        Raises:
            KVStoreException: If the operation fails
        """
        self._ensure_connected()

        try:
            services = []

            # List all keys
            assert self._kv_store is not None  # Type guard for mypy
            keys = await self._kv_store.keys()

            # Get all values
            for key in keys:
                entry = await self._kv_store.get(key)
                if entry and entry.value:
                    if isinstance(entry.value, dict):
                        services.append(ServiceDefinition(**entry.value))
                    else:
                        data = (
                            json.loads(entry.value) if isinstance(entry.value, str) else entry.value
                        )
                        services.append(ServiceDefinition(**data))

            logger.info(f"Listed {len(services)} service definitions")
            return services

        except Exception as e:
            logger.error(f"Failed to list keys: {e}")
            raise KVStoreException(f"Failed to list keys: {e}") from e

    async def get_with_revision(self, key: str) -> tuple[ServiceDefinition | None, int | None]:
        """Get a service definition with its revision number.

        Args:
            key: The service name

        Returns:
            Tuple of (ServiceDefinition, revision) or (None, None) if not found
        """
        self._ensure_connected()

        try:
            assert self._kv_store is not None  # Type guard for mypy
            entry = await self._kv_store.get(key)
            if entry and entry.value:
                if isinstance(entry.value, dict):
                    service = ServiceDefinition(**entry.value)
                else:
                    data = json.loads(entry.value) if isinstance(entry.value, str) else entry.value
                    service = ServiceDefinition(**data)
                return service, entry.revision
            return None, None
        except Exception as e:
            logger.error(f"Failed to get key '{key}' with revision: {e}")
            raise KVStoreException(f"Failed to get key '{key}' with revision: {e}") from e
