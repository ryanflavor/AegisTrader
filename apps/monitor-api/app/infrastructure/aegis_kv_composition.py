"""Alternative design using composition pattern.

This approach creates a clean separation between AegisSDK usage
and KV Store functionality.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import nats
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from nats.js.api import KeyValueConfig
from nats.js.errors import BucketNotFoundError

from ..domain.exceptions import (
    KVStoreException,
)
from ..ports.kv_store import KVStorePort

if TYPE_CHECKING:
    from nats.aio.client import Client as NATSClient
    from nats.js import JetStreamContext
    from nats.js.kv import KeyValue

logger = logging.getLogger(__name__)


class AegisKVStoreComposition(KVStorePort):
    """KV Store adapter using composition with AegisSDK.

    This design uses AegisSDK for standard messaging operations
    while maintaining a separate NATS connection for KV Store.
    """

    def __init__(self, bucket_name: str = "service-registry"):
        """Initialize the KV Store adapter."""
        self.bucket_name = bucket_name
        self._messaging_adapter = NATSAdapter(pool_size=1, use_msgpack=False)
        self._kv_client: NATSClient | None = None
        self._js: JetStreamContext | None = None
        self._kv: KeyValue | None = None

    async def connect(self, nats_url: str) -> None:
        """Connect to NATS for both messaging and KV Store."""
        try:
            # Connect messaging adapter for other operations
            servers = [nats_url]
            await self._messaging_adapter.connect(servers)

            # Separate connection for KV Store operations
            # This maintains clean separation of concerns
            self._kv_client = await nats.connect(nats_url)
            self._js = self._kv_client.jetstream()

            # Create or get the KV bucket
            try:
                self._kv = await self._js.key_value(self.bucket_name)
                logger.info(f"Connected to existing KV bucket: {self.bucket_name}")
            except BucketNotFoundError:
                config = KeyValueConfig(
                    bucket=self.bucket_name,
                    description="Service registry definitions",
                    max_value_size=1024 * 1024,
                    history=10,
                )
                self._kv = await self._js.create_key_value(config)
                logger.info(f"Created new KV bucket: {self.bucket_name}")

        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise KVStoreException(f"Failed to connect to NATS: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        await self._messaging_adapter.disconnect()
        if self._kv_client:
            await self._kv_client.close()
        logger.info("Disconnected from NATS")

    def get_messaging_adapter(self) -> NATSAdapter:
        """Get the AegisSDK adapter for messaging operations."""
        return self._messaging_adapter

    # Rest of KVStorePort implementation...
