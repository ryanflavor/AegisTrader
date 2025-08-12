"""Infrastructure Adapters - DEPRECATED: Use SDK implementations directly.

⚠️ WARNING: These adapters are unnecessary wrappers!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This file contains 357 lines of code that duplicate SDK functionality:

1. LoggingAdapter (24 lines) → Use aegis_sdk.infrastructure.simple_logger.SimpleLogger
2. EnvironmentConfigurationAdapter (31 lines) → Use environment variables directly
3. AegisServiceBusAdapter (117 lines) → Use aegis_sdk.infrastructure.nats_adapter.NATSAdapter
4. KVRegistryAdapter (77 lines) → Use aegis_sdk.infrastructure.kv_service_registry.KVServiceRegistry

❌ DON'T DO THIS:
```python
# Creating unnecessary wrappers around SDK components
class LoggingAdapter(LoggerPort):
    def log(self, level, message, **context):
        # Reimplementing what SimpleLogger already does

class AegisServiceBusAdapter(ServiceBusPort):
    async def register_handler(self, subject, handler):
        # Wrapping NATSAdapter which already works perfectly
```

✅ DO THIS INSTEAD:
```python
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry

# Use SDK components directly
logger = SimpleLogger(service_name)
nats = NATSAdapter()
registry = KVServiceRegistry(kv_store)

# Or even better, let SDK Service handle everything:
service = Service(
    message_bus=nats,
    logger=logger,
    service_registry=registry,
    # ... SDK manages all these components
)
```

The original implementation is preserved below to show the anti-pattern.
Each adapter adds unnecessary complexity without adding value.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Any

from aegis_sdk.infrastructure.serialization import serialize_dict

from type_definitions.interfaces import (
    ConfigurationPort,
    LoggerPort,
    ServiceBusPort,
    ServiceRegistryPort,
)


class LoggingAdapter(LoggerPort):
    """
    DEPRECATED: Use aegis_sdk.infrastructure.simple_logger.SimpleLogger

    This adapter just wraps Python's logging module.
    SDK's SimpleLogger already does this better with proper formatting.
    """

    def __init__(self, service_name: str):
        """Initialize the logging adapter."""
        self.logger = logging.getLogger(service_name)

    def log(self, level: str, message: str, **context: Any) -> None:
        """Log a message with context - SDK SimpleLogger does this better."""
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        if context:
            log_method(f"{message} - {json.dumps(context)}")
        else:
            log_method(message)


class EnvironmentConfigurationAdapter(ConfigurationPort):
    """
    DEPRECATED: Just use os.getenv() directly or SDK's configuration.

    This adapter adds no value - it's just a wrapper around os.environ.
    The SDK Service class handles configuration internally.
    """

    def __init__(self):
        """Initialize with environment variables."""
        self._config = dict(os.environ)

    def get_config(self, key: str, default: str | None = None) -> str | None:
        """Get configuration value - Just use os.getenv() instead."""
        return self._config.get(key, default)

    def set_config(self, key: str, value: str) -> None:
        """Set configuration value - Rarely needed, just use os.environ."""
        self._config[key] = value
        os.environ[key] = value


class AegisServiceBusAdapter(ServiceBusPort):
    """
    DEPRECATED: Use aegis_sdk.infrastructure.nats_adapter.NATSAdapter directly.

    This is a 117-line wrapper around NATSAdapter that adds no value.
    The SDK Service class uses NATSAdapter directly as message_bus.

    Instead of wrapping, just use:
    - service.register_rpc_method() for RPC handlers
    - nats.publish() for publishing
    - nats.subscribe() for subscriptions
    """

    def __init__(self, nats_adapter: Any, logger: LoggerPort):
        """Initialize the service bus adapter."""
        self.nats = nats_adapter
        self.logger = logger
        self.handlers: dict[str, Any] = {}

    async def publish(self, subject: str, message: dict[str, Any]) -> None:
        """Publish a message - Use nats.publish() directly."""
        try:
            # SDK's serialize_dict handles datetime serialization
            data = serialize_dict(message)
            await self.nats.publish(subject, json.dumps(data).encode())
            self.logger.log("debug", f"Published to {subject}", message_preview=str(message)[:100])
        except Exception as e:
            self.logger.log("error", f"Failed to publish to {subject}", error=str(e))
            raise

    async def subscribe(self, subject: str, handler: Callable) -> None:
        """Subscribe to a subject - SDK Service handles this automatically."""

        async def wrapped_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await handler(data)
            except Exception as e:
                self.logger.log("error", f"Handler error for {subject}", error=str(e))

        await self.nats.subscribe(subject, wrapped_handler)
        self.logger.log("info", f"Subscribed to {subject}")

    async def register_handler(self, subject: str, handler: Callable) -> None:
        """
        Register RPC handler - Use service.register_rpc_method() instead.

        The SDK Service class provides this functionality with:
        await service.register_rpc_method("method_name", handler)
        """
        self.handlers[subject] = handler

        async def rpc_wrapper(msg):
            try:
                # Parse request
                request_data = json.loads(msg.data.decode()) if msg.data else {}

                # Call handler
                response = await handler(request_data)

                # Serialize response using SDK utility
                response_data = serialize_dict(response) if response else {}

                # Send reply
                await self.nats.publish(msg.reply, json.dumps(response_data).encode())

            except Exception as e:
                self.logger.log("error", f"RPC handler error for {subject}", error=str(e))
                error_response = {"error": str(e)}
                await self.nats.publish(msg.reply, json.dumps(error_response).encode())

        # Subscribe to RPC subject
        await self.nats.subscribe(subject, rpc_wrapper)
        self.logger.log("info", f"Registered RPC handler for {subject}")


class KVRegistryAdapter(ServiceRegistryPort):
    """
    DEPRECATED: Use aegis_sdk.infrastructure.kv_service_registry.KVServiceRegistry

    This adapter reimplements what KVServiceRegistry already does perfectly.
    The SDK Service class uses KVServiceRegistry directly for registration.

    No need to wrap it - just use:
    registry = KVServiceRegistry(kv_store)
    """

    def __init__(self, kv_store: Any, logger: LoggerPort):
        """Initialize the KV registry adapter."""
        self.kv_store = kv_store
        self.logger = logger

    async def register(self, service_name: str, instance_id: str, metadata: dict[str, Any]) -> None:
        """Register a service - SDK Service does this automatically."""
        key = f"{service_name}/{instance_id}"
        value = {"instance_id": instance_id, "status": "running", **metadata}

        # SDK's KVServiceRegistry handles TTL and heartbeat
        await self.kv_store.put(key, json.dumps(value), ttl=60)
        self.logger.log("info", f"Registered service {key}")

    async def deregister(self, service_name: str, instance_id: str) -> None:
        """Deregister a service - SDK Service handles this in stop()."""
        key = f"{service_name}/{instance_id}"
        await self.kv_store.delete(key)
        self.logger.log("info", f"Deregistered service {key}")

    async def health_check(self, service_name: str, instance_id: str) -> None:
        """Update health check - SDK Service handles heartbeat automatically."""
        key = f"{service_name}/{instance_id}"
        try:
            # Get current value
            entry = await self.kv_store.get(key)
            if entry and entry.value:
                value = json.loads(entry.value)
                value["last_heartbeat"] = serialize_dict({"timestamp": "now"})["timestamp"]

                # Update with new TTL - SDK handles this automatically
                await self.kv_store.put(key, json.dumps(value), ttl=60)
                self.logger.log("debug", f"Health check updated for {key}")
        except Exception as e:
            self.logger.log("error", f"Health check failed for {key}", error=str(e))
