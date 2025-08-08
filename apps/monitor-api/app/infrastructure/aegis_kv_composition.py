"""Alternative design using composition pattern following DDD principles.

This approach creates a clean separation between AegisSDK usage
and KV Store functionality, acting as an Anti-Corruption Layer.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore

from ..domain.exceptions import KVStoreException
from ..domain.models import ServiceDefinition
from ..ports.service_registry_kv_store import ServiceRegistryKVStorePort

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AegisKVStoreComposition(ServiceRegistryKVStorePort):
    """KV Store adapter using composition with AegisSDK following hexagonal architecture.

    This design uses AegisSDK's infrastructure components (NATSAdapter, NATSKVStore)
    in a composition pattern, providing clean separation between the monitor-api
    bounded context and the SDK bounded context.
    """

    def __init__(self, bucket_name: str = "service_registry"):
        """Initialize the KV Store adapter with composition."""
        self.bucket_name = bucket_name
        self._nats_adapter: NATSAdapter | None = None
        self._kv_store: NATSKVStore | None = None
        self._connected = False

    async def connect(self, nats_url: str) -> None:
        """Connect to NATS using SDK's infrastructure components.

        This follows the hexagonal architecture pattern where infrastructure
        adapters are composed to provide functionality.
        """
        try:
            # Initialize NATS adapter (infrastructure layer)
            self._nats_adapter = NATSAdapter()
            await self._nats_adapter.connect([nats_url])

            # Initialize KV Store using the adapter
            self._kv_store = NATSKVStore(self._nats_adapter)
            await self._kv_store.connect(self.bucket_name)

            self._connected = True
            logger.info(f"Connected to NATS KV Store bucket: {self.bucket_name}")

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
        """Retrieve a service definition by key."""
        self._ensure_connected()
        try:
            assert self._kv_store is not None
            entry = await self._kv_store.get(key)
            if entry and entry.value:
                if isinstance(entry.value, dict):
                    return ServiceDefinition(**entry.value)
                else:
                    data = json.loads(entry.value) if isinstance(entry.value, str) else entry.value
                    return ServiceDefinition(**data)
            return None
        except Exception as e:
            logger.error(f"Failed to get key '{key}': {e}")
            raise KVStoreException(f"Failed to get key '{key}': {e}") from e

    async def put(self, key: str, value: ServiceDefinition) -> None:
        """Store a service definition."""
        self._ensure_connected()
        try:
            assert self._kv_store is not None
            existing = await self._kv_store.exists(key)
            if existing:
                raise ValueError(f"Key '{key}' already exists")
            data = value.to_iso_dict()
            await self._kv_store.put(key, data)
            logger.info(f"Stored service definition: {key}")
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to put key '{key}': {e}")
            raise KVStoreException(f"Failed to put key '{key}': {e}") from e

    async def update(self, key: str, value: ServiceDefinition, revision: int | None = None) -> None:
        """Update an existing service definition."""
        self._ensure_connected()
        try:
            assert self._kv_store is not None
            existing = await self._kv_store.get(key)
            if not existing:
                raise ValueError(f"Key '{key}' not found")
            data = value.to_iso_dict()
            if revision is not None:
                from aegis_sdk.domain.models import KVOptions

                options = KVOptions(revision=revision)
                await self._kv_store.put(key, data, options)
            else:
                await self._kv_store.put(key, data)
            logger.info(f"Updated service definition: {key}")
        except ValueError:
            raise
        except Exception as e:
            if "Revision mismatch" in str(e) or "expected" in str(e):
                raise ValueError(f"Revision mismatch for key '{key}'")
            logger.error(f"Failed to update key '{key}': {e}")
            raise KVStoreException(f"Failed to update key '{key}': {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a service definition."""
        self._ensure_connected()
        try:
            assert self._kv_store is not None
            existing = await self._kv_store.exists(key)
            if not existing:
                raise ValueError(f"Key '{key}' not found")
            await self._kv_store.delete(key)
            logger.info(f"Deleted service definition: {key}")
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete key '{key}': {e}")
            raise KVStoreException(f"Failed to delete key '{key}': {e}") from e

    async def list_all(self) -> list[ServiceDefinition]:
        """List all service definitions."""
        self._ensure_connected()
        try:
            services = []
            assert self._kv_store is not None
            keys = await self._kv_store.keys()
            for key in keys:
                if key.startswith("service-instances_"):
                    continue
                entry = await self._kv_store.get(key)
                if entry and entry.value:
                    try:
                        if isinstance(entry.value, dict):
                            services.append(ServiceDefinition(**entry.value))
                        else:
                            data = (
                                json.loads(entry.value)
                                if isinstance(entry.value, str)
                                else entry.value
                            )
                            services.append(ServiceDefinition(**data))
                    except Exception as e:
                        logger.warning(f"Failed to parse service definition for key '{key}': {e}")
                        continue
            logger.info(f"Listed {len(services)} service definitions")
            return services
        except Exception as e:
            logger.error(f"Failed to list keys: {e}")
            raise KVStoreException(f"Failed to list keys: {e}") from e

    @property
    def raw_kv(self) -> Any:
        """Get the raw NATS KV Store for direct operations."""
        if self._kv_store:
            return self._kv_store._kv
        return None

    async def get_with_revision(self, key: str) -> tuple[ServiceDefinition | None, int | None]:
        """Get a service definition with its revision number."""
        self._ensure_connected()
        try:
            assert self._kv_store is not None
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

    def get_messaging_adapter(self) -> NATSAdapter | None:
        """Get the AegisSDK adapter for messaging operations."""
        return self._nats_adapter
