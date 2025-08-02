"""NATS KV Store adapter - Concrete implementation of KVStorePort."""

import json
from collections.abc import AsyncIterator
from typing import Any

from nats.js.kv import KeyValue

from ..domain.models import KVEntry, KVOptions, KVWatchEvent
from ..ports.kv_store import KVStorePort
from ..ports.message_bus import MessageBusPort
from ..ports.metrics import MetricsPort
from .in_memory_metrics import InMemoryMetrics
from .nats_adapter import NATSAdapter


class NATSKVStore(KVStorePort):
    """NATS implementation of the KV Store port.

    This adapter uses NATS JetStream Key-Value store for distributed
    key-value storage with strong consistency guarantees.
    """

    def __init__(
        self,
        nats_adapter: MessageBusPort | None = None,
        metrics: MetricsPort | None = None,
        sanitize_keys: bool = True,
    ):
        """Initialize NATS KV Store adapter.

        Args:
            nats_adapter: Optional NATS adapter. If not provided, creates a new one.
            metrics: Optional metrics port. If not provided, uses default adapter.
            sanitize_keys: Whether to sanitize keys for NATS compatibility (default: True)
        """
        self._nats_adapter = nats_adapter or NATSAdapter()
        self._metrics = metrics or InMemoryMetrics()
        self._kv: KeyValue | None = None
        self._bucket_name: str | None = None
        self._sanitize_keys = sanitize_keys
        # Keep mapping of original to sanitized keys
        self._key_mapping: dict[str, str] = {}

    def _sanitize_key(self, key: str) -> str:
        """Sanitize key to be compatible with NATS KV restrictions.

        NATS KV keys cannot contain: spaces, tabs, '.', '*', '>', '/', '\\'
        We'll replace invalid characters with '_'
        """
        if not self._sanitize_keys:
            return key

        # Replace invalid characters
        sanitized = key
        for char in [" ", "\t", ".", "*", ">", "/", "\\", ":"]:
            sanitized = sanitized.replace(char, "_")

        # Store mapping
        if sanitized != key:
            self._key_mapping[sanitized] = key

        return sanitized

    def _get_original_key(self, sanitized_key: str) -> str:
        """Get the original key from a sanitized key."""
        return self._key_mapping.get(sanitized_key, sanitized_key)

    async def connect(self, bucket: str) -> None:
        """Connect to a KV store bucket."""
        # Ensure NATS adapter is connected
        if not await self._nats_adapter.is_connected():
            raise Exception("NATS adapter not connected")

        if not hasattr(self._nats_adapter, "_js") or not self._nats_adapter._js:
            raise Exception("NATS JetStream not initialized")

        try:
            # Try to get existing bucket first
            try:
                self._kv = await self._nats_adapter._js.key_value(bucket)
            except Exception:
                # Bucket doesn't exist, create it
                config = {
                    "bucket": bucket,
                    "history": 10,  # Keep last 10 revisions
                    "ttl": 0,  # No default TTL
                    "max_value_size": 1024 * 1024,  # 1MB max value size
                    "storage": "file",  # Use file storage for persistence
                }
                self._kv = await self._nats_adapter._js.create_key_value(**config)

            self._bucket_name = bucket
            self._metrics.gauge("kv.buckets.active", 1)
            print(f"✅ Connected to NATS KV bucket: {bucket}")
        except Exception as e:
            self._metrics.increment("kv.connect.error")
            raise Exception(f"Failed to connect to KV bucket '{bucket}': {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from the KV store."""
        self._kv = None
        self._bucket_name = None
        self._key_mapping.clear()
        self._metrics.gauge("kv.buckets.active", 0)

    async def is_connected(self) -> bool:
        """Check if connected to the KV store."""
        return self._kv is not None

    # Basic Operations
    async def get(self, key: str) -> KVEntry | None:
        """Get a value by key."""
        if not self._kv:
            raise Exception("KV store not connected")

        # Sanitize key
        safe_key = self._sanitize_key(key)

        with self._metrics.timer(f"kv.get.{self._bucket_name}"):
            try:
                entry = await self._kv.get(safe_key)

                # Deserialize value
                value = json.loads(entry.value.decode()) if entry.value else None

                # Convert to domain model - handle delta being None
                ttl = None
                if hasattr(entry, "delta") and entry.delta is not None and entry.delta > 0:
                    ttl = entry.delta

                # Handle created timestamp - it might be None for some NATS versions
                from datetime import UTC, datetime

                if entry.created and hasattr(entry.created, "isoformat"):
                    created_at = entry.created.isoformat()
                    updated_at = entry.created.isoformat()
                else:
                    # Use current time as fallback
                    now = datetime.now(UTC).isoformat()
                    created_at = now
                    updated_at = now

                result = KVEntry(
                    key=key,  # Return original key, not sanitized
                    value=value,
                    revision=entry.revision or 0,  # Ensure revision is never None
                    created_at=created_at,
                    updated_at=updated_at,
                    ttl=ttl,
                )

                self._metrics.increment("kv.get.success")
                return result

            except Exception:
                self._metrics.increment("kv.get.miss")
                return None

    async def put(self, key: str, value: Any, options: KVOptions | None = None) -> int:
        """Put a value with optional TTL and revision check."""
        if not self._kv:
            raise Exception("KV store not connected")

        # Sanitize key
        safe_key = self._sanitize_key(key)

        with self._metrics.timer(f"kv.put.{self._bucket_name}"):
            try:
                # Serialize value
                serialized = json.dumps(value, separators=(",", ":")).encode()

                # Handle options
                if options:
                    if options.create_only:
                        # Use create for exclusive creation
                        revision = await self._kv.create(safe_key, serialized)
                    elif options.update_only:
                        # Use update for existing keys only
                        # If no revision specified, get current revision
                        if options.revision is None:
                            try:
                                current = await self._kv.get(safe_key)
                                last_revision = current.revision
                            except Exception as err:
                                raise ValueError(
                                    "Key does not exist for update_only operation"
                                ) from err
                        else:
                            last_revision = options.revision
                        revision = await self._kv.update(safe_key, serialized, last_revision)
                    else:
                        # Normal put with optional revision check
                        # NATS KV doesn't support revision check on regular put
                        if options.revision is not None:
                            # Get current revision and verify
                            try:
                                current = await self._kv.get(safe_key)
                                if current.revision != options.revision:
                                    raise ValueError(
                                        f"Revision mismatch: expected {options.revision}, got {current.revision}"
                                    )
                            except Exception as err:
                                raise ValueError(
                                    "Key does not exist or revision check failed"
                                ) from err

                        # Put with TTL if specified
                        if options.ttl:
                            # NATS KV doesn't support per-key TTL in put operation
                            # TTL must be configured at bucket level
                            # For now, we'll just put without TTL
                            revision = await self._kv.put(safe_key, serialized)
                        else:
                            revision = await self._kv.put(safe_key, serialized)
                else:
                    # Normal put without options
                    revision = await self._kv.put(safe_key, serialized)

                self._metrics.increment("kv.put.success")
                assert isinstance(revision, int)  # mypy type narrowing
                return revision

            except Exception:
                self._metrics.increment("kv.put.error")
                raise

    async def delete(self, key: str, revision: int | None = None) -> bool:
        """Delete a key with optional revision check."""
        if not self._kv:
            raise Exception("KV store not connected")

        # Sanitize key
        safe_key = self._sanitize_key(key)

        with self._metrics.timer(f"kv.delete.{self._bucket_name}"):
            try:
                if revision is not None:
                    await self._kv.delete(safe_key, last=revision)
                else:
                    await self._kv.delete(safe_key)

                self._metrics.increment("kv.delete.success")
                return True

            except Exception:
                self._metrics.increment("kv.delete.miss")
                return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if not self._kv:
            raise Exception("KV store not connected")

        # Sanitize key
        safe_key = self._sanitize_key(key)

        try:
            await self._kv.get(safe_key)
            return True
        except Exception:
            return False

    # Batch Operations
    async def keys(self, prefix: str = "") -> list[str]:
        """List all keys with optional prefix filter."""
        if not self._kv:
            raise Exception("KV store not connected")

        try:
            all_keys = await self._kv.keys()

            # Convert sanitized keys back to original
            original_keys = []
            for safe_key in all_keys:
                original_key = self._get_original_key(safe_key)
                if prefix:
                    if original_key.startswith(prefix):
                        original_keys.append(original_key)
                else:
                    original_keys.append(original_key)

            return original_keys
        except Exception:
            # No keys found
            return []

    async def get_many(self, keys: list[str]) -> dict[str, KVEntry]:
        """Get multiple values by keys."""
        results = {}

        for key in keys:
            entry = await self.get(key)
            if entry:
                results[key] = entry

        return results

    async def put_many(
        self, entries: dict[str, Any], options: KVOptions | None = None
    ) -> dict[str, int]:
        """Put multiple key-value pairs."""
        results = {}

        for key, value in entries.items():
            revision = await self.put(key, value, options)
            results[key] = revision

        return results

    async def delete_many(self, keys: list[str]) -> dict[str, bool]:
        """Delete multiple keys."""
        results = {}

        for key in keys:
            results[key] = await self.delete(key)

        return results

    # Advanced Operations
    async def watch(  # type: ignore[override,misc]
        self, key: str | None = None, prefix: str | None = None
    ) -> AsyncIterator[KVWatchEvent]:
        """Watch for changes to a key or prefix."""
        if key and prefix:
            raise ValueError("Cannot specify both key and prefix")

        if not self._kv:
            raise Exception("KV store not connected")

        # Sanitize key/prefix
        if key:
            safe_key = self._sanitize_key(key)
            watcher = await self._kv.watch(safe_key)
        elif prefix:
            # For prefix watching, we need to watch all and filter
            watcher = await self._kv.watchall()
        else:
            watcher = await self._kv.watchall()

        # Yield events
        async for update in watcher.updates():
            # Get original key
            original_key = self._get_original_key(update.key)

            # Filter by prefix if specified
            if prefix and not original_key.startswith(prefix):
                continue

            # Convert to domain event
            if update.operation == "PUT":
                value = json.loads(update.value.decode()) if update.value else None

                # Handle timestamp
                from datetime import UTC, datetime

                if update.created and hasattr(update.created, "isoformat"):
                    created_at = update.created.isoformat()
                    updated_at = update.created.isoformat()
                else:
                    now = datetime.now(UTC).isoformat()
                    created_at = now
                    updated_at = now

                entry = KVEntry(
                    key=original_key,
                    value=value,
                    revision=update.revision,
                    created_at=created_at,
                    updated_at=updated_at,
                    ttl=update.delta if update.delta and update.delta > 0 else None,
                )
                event = KVWatchEvent(operation="PUT", entry=entry)
            elif update.operation == "DELETE":
                event = KVWatchEvent(operation="DELETE", entry=None)
            elif update.operation == "PURGE":
                event = KVWatchEvent(operation="PURGE", entry=None)
            else:
                continue  # Skip unknown operations

            yield event

    async def history(self, key: str, limit: int = 10) -> list[KVEntry]:
        """Get revision history for a key."""
        if not self._kv:
            raise Exception("KV store not connected")

        # Sanitize key
        safe_key = self._sanitize_key(key)

        try:
            # Get history from NATS KV
            history_entries = await self._kv.history(safe_key)

            # Convert to domain models and limit
            results = []
            for entry in list(history_entries)[:limit]:
                value = json.loads(entry.value.decode()) if entry.value else None

                # Handle timestamp
                from datetime import UTC, datetime

                if entry.created and hasattr(entry.created, "isoformat"):
                    created_at = entry.created.isoformat()
                    updated_at = entry.created.isoformat()
                else:
                    now = datetime.now(UTC).isoformat()
                    created_at = now
                    updated_at = now

                kv_entry = KVEntry(
                    key=key,  # Use original key
                    value=value,
                    revision=entry.revision or 0,  # Ensure revision is never None
                    created_at=created_at,
                    updated_at=updated_at,
                    ttl=entry.delta if entry.delta and entry.delta > 0 else None,
                )
                results.append(kv_entry)

            return results

        except Exception:
            return []

    async def purge(self, key: str) -> None:
        """Purge all revisions of a key."""
        if not self._kv:
            raise Exception("KV store not connected")

        # Sanitize key
        safe_key = self._sanitize_key(key)

        await self._kv.purge(safe_key)
        self._metrics.increment("kv.purge")

    async def clear(self, prefix: str = "") -> int:
        """Clear all keys with optional prefix filter."""
        # Get all matching keys
        keys = await self.keys(prefix)

        # Delete them
        results = await self.delete_many(keys)

        # Count successful deletions
        return sum(1 for success in results.values() if success)

    async def status(self) -> dict[str, Any]:
        """Get KV store status information."""
        if not self._kv:
            return {
                "connected": False,
                "bucket": None,
                "values": 0,
                "history": 0,
                "bytes": 0,
            }

        try:
            # Get bucket status from NATS
            status = await self._kv.status()

            # Build status dict with available fields
            result = {
                "connected": True,
                "bucket": getattr(status, "bucket", self._bucket_name),
            }

            # Add optional fields if they exist
            for field in ["values", "history", "bytes", "ttl", "max_value_size", "max_history"]:
                if hasattr(status, field):
                    result[field] = getattr(status, field)

            return result
        except Exception as e:
            return {
                "connected": True,
                "bucket": self._bucket_name,
                "error": str(e),
            }
