"""Caching layer - Educational Template.

💡 TIP: Consider if you really need caching!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The SDK's KV store can be used for caching with TTL:
✅ aegis_sdk.infrastructure.nats_kv_store.NATSKVStore

Example simple cache using SDK:
"""

from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


class SimpleCache:
    """Simple cache implementation using SDK's KV store.

    Note: The SDK uses msgpack for RPC serialization.
    KV store accepts string values for simplicity.
    """

    def __init__(self, kv_store: NATSKVStore):
        self.kv_store = kv_store

    async def get(self, key: str) -> str | None:
        """Get cached value as string."""
        result = await self.kv_store.get(f"cache:{key}")
        if result and result.value:
            return result.value
        return None

    async def set(self, key: str, value: str, ttl_seconds: int = 300):
        """Set cached value with TTL."""
        await self.kv_store.put(key=f"cache:{key}", value=value, ttl=ttl_seconds)  # Store as string


# TODO: Implement caching if really needed
# Consider: Is the performance gain worth the complexity?
