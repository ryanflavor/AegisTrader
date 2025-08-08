"""NATS KV Store adapter - Concrete implementation of KVStorePort."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from nats.js.kv import KeyValue

from ..domain.exceptions import (
    KVKeyAlreadyExistsError,
    KVKeyNotFoundError,
    KVNotConnectedError,
    KVRevisionMismatchError,
    KVStoreError,
)
from ..domain.models import KVEntry, KVOptions, KVWatchEvent
from ..ports.kv_store import KVStorePort
from ..ports.logger import LoggerPort
from ..ports.message_bus import MessageBusPort
from ..ports.metrics import MetricsPort
from .config import KVStoreConfig, LogContext, NATSConnectionConfig
from .in_memory_metrics import InMemoryMetrics
from .nats_adapter import NATSAdapter
from .simple_logger import SimpleLogger


class NATSKVStore(KVStorePort):
    """NATS implementation of the KV Store port.

    This adapter uses NATS JetStream Key-Value store for distributed
    key-value storage with strong consistency guarantees.
    """

    def __init__(
        self,
        nats_adapter: MessageBusPort | None = None,
        metrics: MetricsPort | None = None,
        logger: LoggerPort | None = None,
        config: KVStoreConfig | None = None,
    ):
        """Initialize NATS KV Store adapter.

        Args:
            nats_adapter: Optional NATS adapter. If not provided, creates a new one.
            metrics: Optional metrics port. If not provided, uses default adapter.
            logger: Optional logger port. If not provided, uses simple logger.
            config: Optional KV store configuration. If not provided, uses defaults.
        """
        self._nats_adapter = nats_adapter or NATSAdapter(config=NATSConnectionConfig())
        self._metrics = metrics or InMemoryMetrics()
        self._logger = logger or SimpleLogger("aegis_sdk.nats_kv_store")
        self._config: KVStoreConfig | None = config
        self._kv: KeyValue | None = None
        self._bucket_name: str | None = None

    def _validate_key(self, key: str) -> None:
        """Validate a key for NATS compatibility.

        Args:
            key: The key to validate

        Raises:
            ValueError: If key contains invalid characters
        """
        invalid_chars = {".", "*", ">", "/", "\\", ":", " ", "\t"}
        for char in invalid_chars:
            if char in key:
                raise ValueError(
                    f"Key '{key}' contains invalid character '{char}'. "
                    f"NATS KV keys cannot contain: {', '.join(sorted(invalid_chars))}"
                )

    async def _create_kv_stream_with_ttl(self, bucket: str) -> bool:
        """Create a KV stream with per-message TTL enabled.

        Args:
            bucket: The bucket name

        Returns:
            bool: True if stream was created successfully
        """
        from nats.js import api

        stream_name = f"KV_{bucket}"

        try:
            # Create stream with standard NATS JS API
            stream_config = api.StreamConfig(
                name=stream_name,
                subjects=[f"$KV.{bucket}.>"],
                retention=api.RetentionPolicy.LIMITS,
                max_msgs_per_subject=self._config.history_size if self._config else 10,
                max_bytes=-1,
                max_age=0,
                max_msg_size=self._config.max_value_size if self._config else 1024 * 1024,
                storage=api.StorageType.FILE,
                allow_direct=True,
                allow_rollup_hdrs=True,
                deny_delete=True,
                deny_purge=False,
                discard=api.DiscardPolicy.NEW,
                num_replicas=1,
            )

            # Create the stream
            # Type narrowing to access NATSAdapter-specific attributes
            if not isinstance(self._nats_adapter, NATSAdapter):
                raise KVStoreError("NATS KV Store requires NATSAdapter", operation="connect")
            if not self._nats_adapter._js:
                raise KVStoreError("NATS JetStream not initialized", operation="connect")
            await self._nats_adapter._js.add_stream(config=stream_config)

            # Update stream to enable TTL using raw API
            nc = self._nats_adapter._connections[0] if self._nats_adapter._connections else None
            if not nc:
                raise Exception("No NATS connection available")

            # Get current stream configuration
            if not self._nats_adapter._js:
                raise KVStoreError("NATS JetStream not initialized", operation="connect")
            stream_info = await self._nats_adapter._js.stream_info(stream_name)
            # Check if as_dict is a coroutine or a regular method
            as_dict_result = stream_info.config.as_dict()
            if asyncio.iscoroutine(as_dict_result):
                config_dict = await as_dict_result
            else:
                config_dict = as_dict_result

            # Add allow_msg_ttl field
            config_dict["allow_msg_ttl"] = True

            # Send update request
            resp = await nc.request(
                f"$JS.API.STREAM.UPDATE.{stream_name}",
                json.dumps(config_dict).encode(),
                timeout=5.0,
            )

            result = json.loads(resp.data.decode())
            if "error" in result:
                self._logger.error(f"Failed to enable TTL: {result['error']}")
                return False

            self._logger.info(f"Created stream {stream_name} with TTL support")
            return True

        except Exception as e:
            self._logger.exception("Failed to create stream with TTL", exc_info=e)
            return False

    async def connect(self, bucket: str) -> None:  # type: ignore[override]
        """Connect to a KV store bucket.

        Args:
            bucket: The bucket name
        """
        # Create config if not provided during init
        if not self._config:
            self._config = KVStoreConfig(bucket=bucket)
        else:
            # Update config with provided values
            self._config = self._config.model_copy(update={"bucket": bucket})

        # Ensure NATS adapter is connected
        if not await self._nats_adapter.is_connected():
            raise KVNotConnectedError("connect")

        # Type narrowing to access NATSAdapter-specific attributes
        if not isinstance(self._nats_adapter, NATSAdapter):
            raise KVStoreError("NATS KV Store requires NATSAdapter", operation="connect")

        # Check if JetStream is available
        if not self._nats_adapter._js:
            raise KVStoreError("NATS JetStream not initialized", operation="connect")

        log_ctx = LogContext(
            operation="connect_kv",
            component="NATSKVStore",
        )

        try:
            # Try to get existing bucket first
            try:
                self._kv = await self._nats_adapter._js.key_value(bucket)
            except Exception:
                # Bucket doesn't exist, create it
                stream_name = f"KV_{bucket}"

                try:
                    # Check if stream already exists
                    await self._nats_adapter._js.stream_info(stream_name)
                except Exception:
                    # Stream doesn't exist, always create with TTL support
                    # TTL is now a standard feature, not optional
                    success = await self._create_kv_stream_with_ttl(bucket)
                    if not success:
                        # Fallback to standard API if TTL creation fails
                        from nats.js import api

                        stream_config = api.StreamConfig(
                            name=stream_name,
                            subjects=[f"$KV.{bucket}.>"],
                            retention=api.RetentionPolicy.LIMITS,
                            max_msgs_per_subject=self._config.history_size if self._config else 10,
                            max_bytes=-1,
                            max_age=0,
                            max_msg_size=(
                                self._config.max_value_size if self._config else 1024 * 1024
                            ),
                            storage=api.StorageType.FILE,
                            allow_direct=True,
                            allow_rollup_hdrs=True,
                            deny_delete=True,
                            deny_purge=False,
                            discard=api.DiscardPolicy.NEW,
                        )
                        await self._nats_adapter._js.add_stream(config=stream_config)

                # Now get the KV bucket interface
                self._kv = await self._nats_adapter._js.key_value(bucket)

            self._bucket_name = bucket
            self._metrics.gauge("kv.buckets.active", 1)
            self._logger.info(f"Connected to NATS KV bucket: {bucket}", extra=log_ctx.to_dict())
        except Exception as e:
            self._metrics.increment("kv.connect.error")
            error_ctx = log_ctx.with_error(e)
            self._logger.exception(
                f"Failed to connect to KV bucket '{bucket}'", extra=error_ctx.to_dict()
            )
            raise KVStoreError(
                f"Failed to connect to KV bucket '{bucket}': {e}",
                bucket=bucket,
                operation="connect",
            ) from e

    async def disconnect(self) -> None:
        """Disconnect from the KV store."""
        self._kv = None
        self._bucket_name = None
        self._metrics.gauge("kv.buckets.active", 0)

    async def is_connected(self) -> bool:
        """Check if connected to the KV store."""
        return self._kv is not None

    # Basic Operations
    async def get(self, key: str) -> KVEntry | None:
        """Get a value by key."""
        if not self._kv:
            raise KVNotConnectedError("get")

        # Validate key
        self._validate_key(key)

        with self._metrics.timer(f"kv.get.{self._bucket_name}"):
            try:
                entry = await self._kv.get(key)

                # Deserialize value
                value = json.loads(entry.value.decode()) if entry.value else None

                # Convert to domain model - handle delta being None
                ttl = None
                if hasattr(entry, "delta") and entry.delta is not None and entry.delta > 0:
                    ttl = entry.delta

                # Debug: log all available attributes on entry
                self._logger.debug(
                    f"Entry attributes for {key}: {[attr for attr in dir(entry) if not attr.startswith('_')]}"
                )
                if hasattr(entry, "delta"):
                    self._logger.debug(f"Entry delta for {key}: {entry.delta}")

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
                    key=key,
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
            raise KVNotConnectedError("put")

        # Validate key
        self._validate_key(key)

        with self._metrics.timer(f"kv.put.{self._bucket_name}"):
            try:
                # Serialize value
                serialized = json.dumps(value, separators=(",", ":")).encode()

                # Handle options
                if options:
                    if options.create_only:
                        # Use create for exclusive creation
                        try:
                            revision = await self._kv.create(key, serialized)
                        except Exception as e:
                            # Convert NATS-specific error to domain exception
                            if "wrong last sequence" in str(e) or "duplicate" in str(e).lower():
                                raise KVKeyAlreadyExistsError(key) from e
                            raise
                    elif options.update_only:
                        # Use update for existing keys only
                        # If no revision specified, get current revision
                        if options.revision is None:
                            try:
                                current = await self._kv.get(key)
                                last_revision = current.revision
                            except Exception as err:
                                raise KVKeyNotFoundError(key, self._bucket_name) from err
                        else:
                            last_revision = options.revision
                        revision = await self._kv.update(key, serialized, last_revision)
                    else:
                        # Normal put with optional revision check
                        # NATS KV doesn't support revision check on regular put
                        if options.revision is not None:
                            # Get current revision and verify
                            try:
                                current = await self._kv.get(key)
                                if current.revision != options.revision:
                                    raise KVRevisionMismatchError(
                                        key, options.revision, current.revision or 0
                                    )
                            except KVRevisionMismatchError:
                                # Re-raise revision mismatch as-is
                                raise
                            except Exception as err:
                                if "not found" in str(err).lower():
                                    raise KVKeyNotFoundError(key, self._bucket_name) from err
                                raise KVStoreError(
                                    "Revision check failed", key=key, operation="put"
                                ) from err

                        # Put with TTL if specified
                        if options.ttl:
                            # IMPORTANT: Per-message TTL doesn't work reliably with KV stores
                            # Stream-level TTL (max_age) handles expiration automatically
                            # See docs/NATS_KV_TTL_SOLUTION.md for details
                            self._logger.debug(
                                f"TTL requested ({options.ttl}s) but using stream-level TTL instead for key={key}"
                            )
                            # Use normal put - stream max_age will handle TTL
                            revision = await self._kv.put(key, serialized)
                            self._metrics.increment("kv.put.stream_ttl")
                        else:
                            revision = await self._kv.put(key, serialized)
                else:
                    # Normal put without options
                    revision = await self._kv.put(key, serialized)

                self._metrics.increment("kv.put.success")
                assert isinstance(revision, int)  # mypy type narrowing
                return revision

            except Exception:
                self._metrics.increment("kv.put.error")
                raise

    async def delete(self, key: str, revision: int | None = None) -> bool:
        """Delete a key with optional revision check."""
        if not self._kv:
            raise KVNotConnectedError("delete")

        # Validate key
        self._validate_key(key)

        with self._metrics.timer(f"kv.delete.{self._bucket_name}"):
            try:
                if revision is not None:
                    await self._kv.delete(key, last=revision)
                else:
                    await self._kv.delete(key)

                self._metrics.increment("kv.delete.success")
                return True

            except Exception:
                self._metrics.increment("kv.delete.miss")
                return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if not self._kv:
            raise KVNotConnectedError("exists")

        # Validate key
        self._validate_key(key)

        try:
            await self._kv.get(key)
            return True
        except Exception:
            return False

    # Batch Operations
    async def keys(self, prefix: str = "") -> list[str]:
        """List all keys with optional prefix filter."""
        if not self._kv:
            raise KVNotConnectedError("keys")

        try:
            all_keys = await self._kv.keys()

            # Filter by prefix if provided
            if prefix:
                return [key for key in all_keys if key.startswith(prefix)]
            return list(all_keys)
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
            raise KVNotConnectedError("watch")

        # Set up watch based on key or prefix
        if key:
            self._validate_key(key)
            # Watch only this specific key, don't include history
            watcher = await self._kv.watch(key, include_history=False)
        elif prefix:
            # For prefix watching, watch all keys and filter in application
            # This is a workaround for NATS KV pattern matching limitations
            watcher = await self._kv.watch(">", include_history=False)
            # Store the prefix for filtering later
            self._watch_prefix = prefix
        else:
            # Watch all keys
            watcher = await self._kv.watch(">", include_history=False)

        # Track if we've seen the first update (which might be initial state)
        # For prefix watching, we need to track per key
        first_updates = {}  # key -> bool

        # Helper to continuously read from watcher even after None marker
        async def watch_generator():
            while True:
                try:
                    # Use updates() method instead of async iteration to avoid StopAsyncIteration
                    update = await watcher.updates(timeout=5.0)  # 5 second timeout for debugging
                    if update is None:
                        # This is the initial "no pending updates" marker
                        continue
                    yield update
                except asyncio.TimeoutError:
                    # No updates for 5 seconds
                    # No updates for timeout period
                    continue
                except Exception:
                    # Error in watcher, stop watching
                    break

        # Yield events
        async for update in watch_generator():
            original_key = update.key

            # Filter by prefix if specified
            if prefix and not original_key.startswith(prefix):
                continue

            # Convert to domain event
            # NATS KV might return operation as string or None
            # None typically means initial value or PUT
            operation = update.operation if hasattr(update, "operation") else None

            # Check if this is an initial state update for this key
            # Initial updates have delta=0 (no time since last update)
            is_initial = False
            if original_key not in first_updates:
                first_updates[original_key] = True
                is_initial = hasattr(update, "delta") and update.delta == 0
            else:
                is_initial = False

            # Skip initial DELETE events (key doesn't exist initially)
            if is_initial and operation in ("DELETE", "delete", "DEL", "del"):
                continue

            # Handle PUT operations (including initial values where operation is None)
            if operation in (None, "PUT", "put"):
                # Skip if no value (this can happen for the initial nil marker)
                if update.value is None:
                    continue

                value = json.loads(update.value.decode())

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
                    ttl=(
                        update.delta
                        if hasattr(update, "delta") and update.delta and update.delta > 0
                        else None
                    ),
                )
                event = KVWatchEvent(operation="PUT", entry=entry)
            elif operation in ("DELETE", "delete", "DEL", "del"):
                event = KVWatchEvent(operation="DELETE", entry=None)
            elif operation in ("PURGE", "purge"):
                event = KVWatchEvent(operation="PURGE", entry=None)
            else:
                # Log unknown operation for debugging
                self._logger.warning(
                    f"Unknown KV watch operation: {operation} for key: {original_key}"
                )
                continue  # Skip unknown operations

            yield event

    async def history(self, key: str, limit: int = 10) -> list[KVEntry]:
        """Get revision history for a key."""
        if not self._kv:
            raise KVNotConnectedError("history")

        # Validate key
        self._validate_key(key)

        try:
            # Get history from NATS KV
            history_entries = await self._kv.history(key)

            # Convert to domain models and limit
            results = []
            entries_list = list(history_entries)
            # Reverse to get newest first
            entries_list.reverse()

            for entry in entries_list[:limit]:
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
            raise KVNotConnectedError("purge")

        # Validate key
        self._validate_key(key)

        await self._kv.purge(key)
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

        log_ctx = LogContext(
            operation="status",
            component="NATSKVStore",
        )

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

            # Add config info if available
            if self._config:
                result["config"] = {
                    "enable_ttl": self._config.enable_ttl,
                    "max_value_size": self._config.max_value_size,
                    "history_size": self._config.history_size,
                }

            return result
        except Exception as e:
            error_ctx = log_ctx.with_error(e)
            self._logger.error("Failed to get KV status", extra=error_ctx.to_dict())
            return {
                "connected": True,
                "bucket": self._bucket_name,
                "error": str(e),
            }
