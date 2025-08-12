"""Port Interfaces - DEPRECATED: Use SDK ports directly.

⚠️ WARNING: Reimplementing SDK port interfaces!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The AegisSDK already provides all necessary port interfaces:

SDK Ports Available:
- aegis_sdk.ports.logger.LoggerPort
- aegis_sdk.ports.message_bus.MessageBusPort
- aegis_sdk.ports.service_registry.ServiceRegistryPort
- aegis_sdk.ports.service_discovery.ServiceDiscoveryPort
- aegis_sdk.ports.clock.ClockPort

❌ DON'T DO THIS:
```python
# Defining your own port interfaces
class LoggerPort(Protocol):
    def log(self, level: str, message: str) -> None: ...

class ServiceBusPort(Protocol):
    async def publish(self, subject: str, message: dict) -> None: ...
```

✅ DO THIS INSTEAD:
```python
from aegis_sdk.ports.logger import LoggerPort
from aegis_sdk.ports.message_bus import MessageBusPort
from aegis_sdk.ports.service_registry import ServiceRegistryPort

# Use SDK ports directly - they're well-tested and complete
```

The interfaces below duplicate SDK functionality.
Keep them only as reference for what NOT to do.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class LoggerPort(Protocol):
    """
    DEPRECATED: Use aegis_sdk.ports.logger.LoggerPort

    SDK already defines this interface with better typing.
    """

    def log(self, level: str, message: str, **context: Any) -> None:
        """Log a message with optional context."""
        ...


class ConfigurationPort(Protocol):
    """
    DEPRECATED: Configuration should be handled via environment variables.

    SDK Service class handles configuration internally.
    No need for a separate configuration port.
    """

    def get_config(self, key: str, default: str | None = None) -> str | None:
        """Get configuration value."""
        ...

    def set_config(self, key: str, value: str) -> None:
        """Set configuration value."""
        ...


class ServiceBusPort(Protocol):
    """
    DEPRECATED: Use aegis_sdk.ports.message_bus.MessageBusPort

    SDK provides a complete MessageBusPort interface.
    The Service class uses it directly.
    """

    async def publish(self, subject: str, message: dict[str, Any]) -> None:
        """Publish a message to a subject."""
        ...

    async def subscribe(self, subject: str, handler: Callable) -> None:
        """Subscribe to a subject with a handler."""
        ...

    async def register_handler(self, subject: str, handler: Callable) -> None:
        """Register an RPC handler for a subject."""
        ...


class ServiceRegistryPort(Protocol):
    """
    DEPRECATED: Use aegis_sdk.ports.service_registry.ServiceRegistryPort

    SDK provides complete service registry interface.
    The Service class handles registration automatically.
    """

    async def register(self, service_name: str, instance_id: str, metadata: dict[str, Any]) -> None:
        """Register a service instance."""
        ...

    async def deregister(self, service_name: str, instance_id: str) -> None:
        """Deregister a service instance."""
        ...

    async def health_check(self, service_name: str, instance_id: str) -> None:
        """Update health check/heartbeat for a service."""
        ...


# Note: These interfaces are kept for backward compatibility
# but should NOT be used in new code. Use SDK ports instead.
