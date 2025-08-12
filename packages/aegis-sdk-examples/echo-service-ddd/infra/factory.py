"""Service Factory - DEPRECATED: Use SDK Service class instead.

⚠️ WARNING: This factory pattern is no longer needed!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This file demonstrates an ANTI-PATTERN. The AegisSDK already provides:
- Service lifecycle management via aegis_sdk.application.service.Service
- Dependency injection through Service constructor
- Automatic heartbeat and registration

❌ DON'T DO THIS:
```python
factory = ServiceFactory()
await factory.initialize(...)
service_bus = factory.get_service_bus()
# ... 277 lines of manual wiring
```

✅ DO THIS INSTEAD:
```python
from aegis_sdk.application.service import Service, ServiceConfig

service = Service(
    service_name=config.service_name,
    message_bus=nats,
    instance_id=config.instance_id,
    service_registry=registry,
    logger=SimpleLogger(service_name),
    heartbeat_interval=10.0,  # SDK handles heartbeat
    enable_registration=True   # SDK handles registration
)
await service.register_rpc_method("echo", handle_echo)
await service.start()  # SDK handles everything!
```

See main.py for the correct implementation using SDK Service class.

This file is kept for educational purposes to show what NOT to do.
Original implementation required 277 lines. SDK approach needs only 20 lines.
"""

# The original factory implementation is preserved below as a reference
# of what you should NOT implement yourself.

from __future__ import annotations

from application.use_cases import EchoUseCase, GetMetricsUseCase, HealthCheckUseCase
from crossdomain.anti_corruption import MonitorAPIAdapter
from domain.services import EchoProcessor, MetricsCollector
from infra.adapters import (
    AegisServiceBusAdapter,
    EnvironmentConfigurationAdapter,
    KVRegistryAdapter,
    LoggingAdapter,
)
from type_definitions.interfaces import (
    ConfigurationPort,
    LoggerPort,
    ServiceBusPort,
    ServiceRegistryPort,
)


class ServiceFactory:
    """
    DEPRECATED: This entire factory is unnecessary overhead.

    The SDK Service class already handles:
    - Component initialization
    - Dependency wiring
    - Lifecycle management
    - Clean shutdown

    Keep this only as an example of over-engineering.
    """

    def __init__(self):
        """Initialize the factory with empty components."""
        # All these components are already provided by SDK
        self.nats_adapter = None
        self.service_bus: ServiceBusPort | None = None
        self.configuration: ConfigurationPort | None = None
        self.registry: ServiceRegistryPort | None = None
        self.logger: LoggerPort | None = None
        self.monitor_api: MonitorAPIAdapter | None = None

        # Domain services (these ARE needed for business logic)
        self.echo_processor: EchoProcessor | None = None
        self.metrics_collector: MetricsCollector | None = None

    async def initialize(
        self,
        nats_url: str,
        service_name: str,
        version: str,
        instance_id: str,
        monitor_api_url: str | None = None,
    ) -> None:
        """
        Initialize all components and wire dependencies.

        ⚠️ SDK Service class does this automatically in its constructor!
        No need for manual initialization.
        """
        # This entire initialization is handled by SDK Service class
        from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
        from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore

        # Configuration adapter - SDK has this built-in
        self.configuration = EnvironmentConfigurationAdapter()
        self.configuration.set_config("SERVICE_NAME", service_name)
        self.configuration.set_config("SERVICE_VERSION", version)
        self.configuration.set_config("SERVICE_INSTANCE_ID", instance_id)

        # Logger - Use SDK's SimpleLogger instead
        self.logger = LoggingAdapter(service_name)

        # NATS connection - SDK Service handles this
        self.nats_adapter = NATSAdapter()
        await self.nats_adapter.connect(nats_url)

        # Service bus adapter - Unnecessary wrapper around SDK's NATSAdapter
        self.service_bus = AegisServiceBusAdapter(self.nats_adapter, self.logger)

        # KV Store and Registry - SDK provides these
        kv_store = NATSKVStore(self.nats_adapter)
        await kv_store.connect("service_registry")
        self.registry = KVRegistryAdapter(kv_store, self.logger)

        # Register service - SDK Service does this automatically
        await self.registry.register(service_name, instance_id, {"version": version})

        # Monitor API adapter - Could be added to SDK as a feature
        if monitor_api_url:
            self.monitor_api = MonitorAPIAdapter(monitor_api_url, self.logger)

        # Initialize domain services (KEEP THESE - they're business logic)
        self.echo_processor = EchoProcessor()
        self.metrics_collector = MetricsCollector()

        self.logger.log("info", "ServiceFactory initialized", service=service_name)

    def get_service_bus(self) -> ServiceBusPort:
        """Get the service bus adapter - SDK provides message_bus directly."""
        if not self.service_bus:
            raise RuntimeError("ServiceFactory not initialized")
        return self.service_bus

    def get_echo_use_case(self) -> EchoUseCase:
        """Get echo use case - This is valid DDD, keep for business logic."""
        if not self.echo_processor or not self.metrics_collector:
            raise RuntimeError("Domain services not initialized")
        return EchoUseCase(self.echo_processor, self.metrics_collector)

    def get_metrics_use_case(self) -> GetMetricsUseCase:
        """Get metrics use case - This is valid DDD, keep for business logic."""
        if not self.metrics_collector:
            raise RuntimeError("MetricsCollector not initialized")
        return GetMetricsUseCase(self.metrics_collector)

    def get_health_check_use_case(self) -> HealthCheckUseCase:
        """Get health check use case - SDK Service provides health endpoint."""
        return HealthCheckUseCase()

    async def shutdown(self) -> None:
        """
        Clean shutdown of all components.

        ⚠️ SDK Service.stop() handles all cleanup automatically!
        """
        if self.registry and self.configuration:
            service_name = self.configuration.get_config("SERVICE_NAME")
            instance_id = self.configuration.get_config("SERVICE_INSTANCE_ID")
            if service_name and instance_id:
                await self.registry.deregister(service_name, instance_id)

        if self.nats_adapter:
            await self.nats_adapter.disconnect()

        if self.logger:
            self.logger.log("info", "ServiceFactory shutdown complete")
