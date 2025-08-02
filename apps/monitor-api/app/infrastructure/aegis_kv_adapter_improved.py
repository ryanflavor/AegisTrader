"""Improved NATS KV Store adapter using AegisSDK.

This shows how the adapter could be implemented if AegisSDK
exposed proper KV Store functionality.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from nats.js.api import KeyValueConfig
from nats.js.errors import BucketNotFoundError

from ..domain.exceptions import (
    KVStoreException,
)
from ..ports.kv_store import KVStorePort

if TYPE_CHECKING:
    from nats.js.kv import KeyValue

logger = logging.getLogger(__name__)


class ImprovedAegisKVStoreAdapter(KVStorePort):
    """Improved NATS KV Store adapter using AegisSDK.

    This implementation assumes AegisSDK has been extended with:
    - get_jetstream() method to access JetStream context
    - Or direct KV Store methods like get_kv_store(bucket_name)
    """

    def __init__(self, bucket_name: str = "service-registry"):
        """Initialize the KV Store adapter.

        Args:
            bucket_name: Name of the KV bucket (default: "service-registry")
        """
        self.bucket_name = bucket_name
        self._adapter = NATSAdapter(pool_size=1, use_msgpack=False)
        self._kv: KeyValue | None = None

    async def connect(self, nats_url: str) -> None:
        """Connect to NATS using AegisSDK and initialize KV Store."""
        try:
            # Connect using AegisSDK
            servers = [nats_url]
            await self._adapter.connect(servers)

            # PROPOSED: AegisSDK should expose this method
            js = await self._adapter.get_jetstream()

            # Or even better, AegisSDK could provide direct KV access:
            # self._kv = await self._adapter.get_kv_store(self.bucket_name, create_if_missing=True)

            # Create or get the KV bucket
            try:
                self._kv = await js.key_value(self.bucket_name)
                logger.info(f"Connected to existing KV bucket: {self.bucket_name}")
            except BucketNotFoundError:
                # Create the bucket if it doesn't exist
                config = KeyValueConfig(
                    bucket=self.bucket_name,
                    description="Service registry definitions",
                    max_value_size=1024 * 1024,  # 1MB max per value
                    history=10,  # Keep 10 versions
                )
                self._kv = await js.create_key_value(config)
                logger.info(f"Created new KV bucket: {self.bucket_name}")

        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise KVStoreException(f"Failed to connect to NATS: {e}") from e

    # Rest of the implementation remains the same...
