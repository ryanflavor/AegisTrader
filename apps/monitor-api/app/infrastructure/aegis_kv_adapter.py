"""NATS KV Store adapter using AegisSDK.

This module implements the KVStorePort interface using AegisSDK's NATS adapter.
Since AegisSDK doesn't directly expose KV Store functionality, we extend it.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from nats.js.api import KeyValueConfig
from nats.js.errors import BucketNotFoundError, KeyNotFoundError, NoKeysError

from ..domain.exceptions import (
    ConcurrentUpdateException,
    KVStoreException,
    ServiceAlreadyExistsException,
    ServiceNotFoundException,
)
from ..domain.models import ServiceDefinition
from ..ports.kv_store import KVStorePort

if TYPE_CHECKING:
    from nats.js import JetStreamContext
    from nats.js.kv import KeyValue

logger = logging.getLogger(__name__)


class AegisKVStoreAdapter(KVStorePort):
    """NATS KV Store adapter using AegisSDK.

    This adapter extends AegisSDK's NATSAdapter to provide KV Store functionality
    while maintaining consistency with the SDK's architecture.
    """

    def __init__(self, bucket_name: str = "service-registry"):
        """Initialize the KV Store adapter.

        Args:
            bucket_name: Name of the KV bucket (default: "service-registry")
        """
        self.bucket_name = bucket_name
        self._adapter = NATSAdapter(pool_size=1, use_msgpack=False)
        self._kv: KeyValue | None = None
        self._js: JetStreamContext | None = None

    async def connect(self, nats_url: str) -> None:
        """Connect to NATS using AegisSDK and initialize KV Store.

        Args:
            nats_url: NATS server URL

        Raises:
            KVStoreException: If connection fails
        """
        try:
            # Connect using AegisSDK
            servers = [nats_url]
            await self._adapter.connect(servers)

            # Access JetStream context from the adapter
            # Note: This accesses a private attribute, but it's the only way
            # to get the JetStream context from AegisSDK currently
            if hasattr(self._adapter, "_js") and self._adapter._js:
                self._js = self._adapter._js
            else:
                # If AegisSDK doesn't expose JetStream, we need to get it from the connection
                if hasattr(self._adapter, "_connections") and self._adapter._connections:
                    nc = self._adapter._connections[0]
                    self._js = nc.jetstream()
                else:
                    raise KVStoreException("Unable to access NATS JetStream from AegisSDK")

            # Create or get the KV bucket
            try:
                self._kv = await self._js.key_value(self.bucket_name)
                logger.info(f"Connected to existing KV bucket: {self.bucket_name}")
            except BucketNotFoundError:
                # Create the bucket if it doesn't exist
                config = KeyValueConfig(
                    bucket=self.bucket_name,
                    description="Service registry definitions",
                    max_value_size=1024 * 1024,  # 1MB max per value
                    history=10,  # Keep 10 versions
                )
                self._kv = await self._js.create_key_value(config)
                logger.info(f"Created new KV bucket: {self.bucket_name}")

        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise KVStoreException(f"Failed to connect to NATS: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from NATS using AegisSDK."""
        await self._adapter.disconnect()
        logger.info("Disconnected from NATS")

    def _ensure_connected(self) -> None:
        """Ensure we're connected to NATS."""
        if not self._kv:
            raise KVStoreException("Not connected to NATS KV Store")
        assert self._kv is not None  # Type hint for mypy

    async def get(self, key: str) -> ServiceDefinition | None:
        """Retrieve a service definition by key."""
        self._ensure_connected()

        try:
            entry = await self._kv.get(key)
            if entry and entry.value:
                data = json.loads(entry.value.decode())
                return ServiceDefinition(**data)
            return None
        except KeyNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to get key '{key}': {e}")
            raise KVStoreException(f"Failed to get key '{key}': {e}") from e

    async def put(self, key: str, value: ServiceDefinition) -> None:
        """Store a service definition."""
        self._ensure_connected()

        try:
            # Check if key already exists
            try:
                existing = await self._kv.get(key)
                if existing and existing.value:
                    raise ServiceAlreadyExistsException(key)
            except KeyNotFoundError:
                # Key doesn't exist, which is what we want
                pass

            # Store the new value
            data = value.model_dump_json()
            await self._kv.put(key, data.encode())
            logger.info(f"Stored service definition: {key}")

        except ServiceAlreadyExistsException:
            raise
        except Exception as e:
            logger.error(f"Failed to put key '{key}': {e}")
            raise KVStoreException(f"Failed to put key '{key}': {e}") from e

    async def update(self, key: str, value: ServiceDefinition, revision: int | None = None) -> None:
        """Update an existing service definition."""
        self._ensure_connected()

        try:
            # Check if key exists
            existing = await self._kv.get(key)
            if not existing or not existing.value:
                raise ServiceNotFoundException(key)

            data = value.model_dump_json()

            if revision is not None:
                # Use optimistic locking with revision
                await self._kv.update(key, data.encode(), revision)
            else:
                # Update without revision check
                await self._kv.put(key, data.encode())

            logger.info(f"Updated service definition: {key}")

        except ServiceNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to update key '{key}': {e}")
            if "wrong last sequence" in str(e):
                raise ConcurrentUpdateException(key) from e
            raise KVStoreException(f"Failed to update key '{key}': {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a service definition."""
        self._ensure_connected()

        try:
            # Check if key exists
            existing = await self._kv.get(key)
            if not existing or not existing.value:
                raise ServiceNotFoundException(key)

            await self._kv.delete(key)
            logger.info(f"Deleted service definition: {key}")

        except ServiceNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete key '{key}': {e}")
            raise KVStoreException(f"Failed to delete key '{key}': {e}") from e

    async def list_all(self) -> list[ServiceDefinition]:
        """List all service definitions."""
        self._ensure_connected()

        try:
            services = []
            keys = await self._kv.keys()

            for key in keys:
                entry = await self._kv.get(key)
                if entry and entry.value:
                    data = json.loads(entry.value.decode())
                    services.append(ServiceDefinition(**data))

            logger.info(f"Listed {len(services)} service definitions")
            return services

        except NoKeysError:
            # No keys in the bucket yet
            return []
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
            entry = await self._kv.get(key)
            if entry and entry.value:
                data = json.loads(entry.value.decode())
                return ServiceDefinition(**data), entry.revision
            return None, None
        except KeyNotFoundError:
            return None, None
        except Exception as e:
            logger.error(f"Failed to get key '{key}' with revision: {e}")
            raise KVStoreException(f"Failed to get key '{key}' with revision: {e}") from e

    def get_metrics(self) -> dict[str, Any]:
        """Get metrics from the AegisSDK adapter.

        Returns:
            Dictionary of metrics
        """
        if hasattr(self._adapter, "_metrics") and self._adapter._metrics:
            return self._adapter._metrics.get_all()
        return {}
