"""NATS connection adapter implementation."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import nats


class NATSConnectionAdapter:
    """Adapter for NATS connection operations."""

    def __init__(self):
        """Initialize NATS connection adapter."""
        self._client = None
        self._jetstream = None
        # Keep old names for compatibility
        self._nc = None
        self._js = None

    async def connect(self, url: str, timeout: float = 5.0) -> bool:
        """Connect to NATS server."""
        try:
            self._client = await nats.connect(url, connect_timeout=timeout)
            self._nc = self._client  # Compatibility
            self._jetstream = self._client.jetstream()
            self._js = self._jetstream  # Compatibility
            return True
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self._client:
            await self._client.close()
            self._client = None
            self._jetstream = None
            self._nc = None
            self._js = None

    async def is_connected(self) -> bool:
        """Check if connected to NATS."""
        return self._client is not None and self._client.is_connected

    async def get_server_info(self) -> dict[str, Any]:
        """Get NATS server information."""
        if not await self.is_connected():
            raise ConnectionError("Not connected to NATS")

        # Get basic server info
        return {
            "connected": True,
            "client_id": self._client.client_id if self._client else None,
        }

    async def create_kv_bucket(self, bucket: str, ttl_seconds: int = 0) -> bool:
        """Create a KV bucket."""
        if not await self.is_connected():
            return False

        try:
            config = nats.js.api.KeyValueConfig(
                bucket=bucket,
                ttl=ttl_seconds if ttl_seconds > 0 else None,
            )
            await self._jetstream.create_key_value(config)
            return True
        except Exception:
            return False

    async def bucket_exists(self, bucket: str) -> bool:
        """Check if a KV bucket exists."""
        if not await self.is_connected():
            return False

        try:
            await self._jetstream.key_value(bucket)
            return True
        except Exception:
            return False

    async def kv_put(self, bucket: str, key: str, value: Any) -> None:
        """Put value in KV store."""
        if not await self.is_connected():
            return

        try:
            kv = await self._jetstream.key_value(bucket)
            data = json.dumps(value).encode() if not isinstance(value, bytes) else value
            await kv.put(key, data)
        except Exception:
            pass

    async def kv_get(self, bucket: str, key: str) -> Any:
        """Get value from KV store."""
        if not await self.is_connected():
            return None

        try:
            kv = await self._jetstream.key_value(bucket)
            entry = await kv.get(key)
            if entry and entry.value:
                return json.loads(entry.value.decode())
            return None
        except Exception:
            return None

    async def kv_delete(self, bucket: str, key: str) -> None:
        """Delete value from KV store."""
        if not await self.is_connected():
            return

        try:
            kv = await self._jetstream.key_value(bucket)
            await kv.delete(key)
        except Exception:
            pass

    async def publish(self, subject: str, data: bytes) -> None:
        """Publish message to subject."""
        if self._client:
            await self._client.publish(subject, data)

    async def subscribe(self, subject: str, cb=None):
        """Subscribe to subject."""
        if self._client:
            return await self._client.subscribe(subject, cb=cb)
        return None

    async def request(self, subject: str, data: bytes, timeout: float = 1.0):
        """Send request and wait for reply."""
        if self._client:
            return await self._client.request(subject, data, timeout=timeout)
        return None
