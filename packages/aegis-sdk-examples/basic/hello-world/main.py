"""Main entry point for Hello World service."""

import asyncio
import os

from aegis_sdk_dev.quickstart.bootstrap import cleanup_service_context, create_service_context
from application.use_cases import HealthCheckUseCase, HelloUseCase
from domain.models import HelloRequest
from infrastructure.adapters import (
    create_audit_adapter,
    create_metrics_adapter,
    create_notification_adapter,
)
from pydantic import BaseModel


class ServiceConfig(BaseModel):
    """Service configuration."""

    nats_url: str = "nats://localhost:4222"
    service_name: str = "hello-world-service"
    enable_metrics: bool = True
    enable_audit: bool = True
    enable_notifications: bool = True

    model_config = {"strict": True}


class HelloWorldService:
    """Main service class following hexagonal architecture."""

    def __init__(self, config: ServiceConfig):
        """Initialize service with configuration."""
        self.config = config
        self.context: object | None = None
        self.hello_use_case: HelloUseCase | None = None
        self.health_use_case: HealthCheckUseCase | None = None

    async def start(self) -> None:
        """Start the service."""
        print(f"🚀 Starting {self.config.service_name}...")

        # Bootstrap SDK context
        self.context = await create_service_context(
            nats_url=self.config.nats_url,
            service_name=self.config.service_name,
        )

        # Create infrastructure adapters
        metrics = create_metrics_adapter() if self.config.enable_metrics else None
        audit = create_audit_adapter(self.context.logger) if self.config.enable_audit else None
        notification = create_notification_adapter(
            use_nats=self.config.enable_notifications,
            nats_client=self.context.message_bus if self.config.enable_notifications else None,
        )

        # Initialize use cases with dependency injection
        self.hello_use_case = HelloUseCase(
            metrics=metrics,
            audit_log=audit,
            notification=notification,
        )
        self.health_use_case = HealthCheckUseCase(self.hello_use_case)

        # Register message handlers
        await self._register_handlers()

        print(f"✅ {self.config.service_name} started successfully!")
        print(f"📡 Connected to NATS at {self.config.nats_url}")

    async def _register_handlers(self) -> None:
        """Register message handlers."""
        if not self.context:
            return

        # Subscribe to hello requests
        await self.context.message_bus.subscribe("hello.request", self._handle_hello_request)

        # Subscribe to health checks
        await self.context.message_bus.subscribe("hello.health", self._handle_health_check)

    async def _handle_hello_request(self, msg) -> None:
        """Handle incoming hello request."""
        try:
            # Parse request
            data = msg.data.decode() if isinstance(msg.data, bytes) else msg.data
            import json

            request_data = json.loads(data)

            # Create domain model from data
            request = HelloRequest(**request_data)

            # Process through use case
            response = await self.hello_use_case.process_hello(request)

            # Send response if reply subject exists
            if hasattr(msg, "reply") and msg.reply:
                await self.context.message_bus.publish(
                    msg.reply, response.model_dump_json().encode()
                )
        except Exception as e:
            print(f"❌ Error processing hello request: {e}")

    async def _handle_health_check(self, msg) -> None:
        """Handle health check request."""
        try:
            health = await self.health_use_case.check_health()

            if hasattr(msg, "reply") and msg.reply:
                import json

                await self.context.message_bus.publish(msg.reply, json.dumps(health).encode())
        except Exception as e:
            print(f"❌ Error processing health check: {e}")

    async def stop(self) -> None:
        """Stop the service."""
        print(f"🛑 Stopping {self.config.service_name}...")
        if self.context:
            await cleanup_service_context(self.context)
        print(f"👋 {self.config.service_name} stopped")

    async def run_forever(self) -> None:
        """Run the service forever."""
        await self.start()
        try:
            # Keep the service running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n⌨️  Received interrupt signal")
        finally:
            await self.stop()


async def main():
    """Main entry point."""
    # Load configuration from environment
    config = ServiceConfig(
        nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
        service_name=os.getenv("SERVICE_NAME", "hello-world-service"),
        enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
        enable_audit=os.getenv("ENABLE_AUDIT", "true").lower() == "true",
        enable_notifications=os.getenv("ENABLE_NOTIFICATIONS", "true").lower() == "true",
    )

    # Create and run service
    service = HelloWorldService(config)
    await service.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
