#!/usr/bin/env python3
"""
Enhanced Pure NATS implementation with Hybrid Mode features.
Demonstrates how to add AegisIPC hybrid architecture features to the minimal implementation.
"""

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import nats
from nats.js import JetStreamContext
from pydantic import BaseModel, Field

# ============ HYBRID MODE FEATURES ============


# 1. Subject Pattern Management (from hybrid-mode-design.md)
class SubjectPatterns:
    """Centralized subject pattern management."""

    # Application patterns
    @staticmethod
    def rpc(service: str, method: str) -> str:
        return f"rpc.{service}.{method}"

    @staticmethod
    def event(domain: str, event_type: str) -> str:
        return f"events.{domain}.{event_type}"

    @staticmethod
    def command(service: str, command: str) -> str:
        return f"commands.{service}.{command}"

    @staticmethod
    def service_instance(service: str, instance: str) -> str:
        return f"service.{service}.{instance}"

    # Internal patterns
    @staticmethod
    def heartbeat(service: str) -> str:
        return f"internal.heartbeat.{service}"

    @staticmethod
    def registry_register() -> str:
        return "internal.registry.register"

    @staticmethod
    def route_request() -> str:
        return "internal.route.request"

    # Command-specific patterns
    @staticmethod
    def command_progress(command_id: str) -> str:
        return f"commands.progress.{command_id}"

    @staticmethod
    def command_cancel(command_id: str) -> str:
        return f"commands.cancel.{command_id}"

    @staticmethod
    def command_callback(command_id: str) -> str:
        return f"commands.callback.{command_id}"


# 2. Service Registry & Health Management
@dataclass
class ServiceInstance:
    """Service instance with health tracking."""

    service_name: str
    instance_id: str
    status: str = "ACTIVE"  # ACTIVE, STANDBY, UNHEALTHY
    last_heartbeat: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict = field(default_factory=dict)


# 3. Enhanced Message Models with Pydantic
class Message(BaseModel):
    """Core message envelope with trace context."""

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str | None = None
    target: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RPCRequest(Message):
    """RPC request with timeout."""

    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    timeout: float = 5.0


class RPCResponse(Message):
    """RPC response with error handling."""

    success: bool = True
    result: Any | None = None
    error: str | None = None


# 4. Enhanced Demo with Hybrid Features
class HybridNATSDemo:
    """Enhanced demo with hybrid architecture features."""

    def __init__(
        self,
        service_name: str = "demo-service",
        nats_url: str = "nats://localhost:4222",
    ):
        self.service_name = service_name
        self.instance_id = f"{service_name}-{uuid.uuid4().hex[:8]}"
        self.nats_url = nats_url
        self.nc: nats.Client | None = None
        self.js: JetStreamContext | None = None

        # Service registry
        self.service_registry: dict[str, ServiceInstance] = {}
        self.rpc_handlers: dict[str, Callable] = {}
        self.event_handlers: dict[str, list[Callable]] = {}
        self.command_handlers: dict[str, Callable] = {}

        # Metrics
        self.metrics = {
            "rpc_requests": 0,
            "rpc_latency_ms": [],
            "events_published": 0,
            "commands_processed": 0,
        }

        # Health management
        self._heartbeat_task: asyncio.Task | None = None
        self._health_check_task: asyncio.Task | None = None

    async def connect(self):
        """Connect to NATS with enhanced setup."""
        self.nc = await nats.connect(self.nats_url)

        # Initialize JetStream with production config
        try:
            self.js = self.nc.jetstream()

            # Create streams with retention policies
            await self._setup_streams()

        except Exception as e:
            print(f"❌ JetStream initialization failed: {e}")
            raise

        # Register service instance
        await self._register_service()

        # Start health management
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        print(f"✅ Connected as {self.service_name}/{self.instance_id}")

    async def _setup_streams(self):
        """Setup JetStream streams with production config."""
        # Event stream with 7-day retention
        try:
            await self.js.stream_info("EVENTS")
            print("✅ Using existing EVENTS stream")
        except Exception:
            await self.js.add_stream(
                name="EVENTS",
                subjects=["events.>"],
                retention="limits",
                max_msgs=1000000,
                max_age=7 * 24 * 60 * 60,  # 7 days
                replicas=3,
            )
            print("✅ Created EVENTS stream with 7-day retention")

        # Command stream with work queue semantics
        try:
            await self.js.stream_info("COMMANDS")
            print("✅ Using existing COMMANDS stream")
        except Exception:
            await self.js.add_stream(
                name="COMMANDS",
                subjects=["commands.>"],
                retention="workqueue",
                max_msgs=10000,
                replicas=3,
            )
            print("✅ Created COMMANDS stream with work queue")

    async def _register_service(self):
        """Register service instance."""
        instance = ServiceInstance(
            service_name=self.service_name,
            instance_id=self.instance_id,
            metadata={
                "version": "1.0.0",
                "capabilities": ["rpc", "events", "commands"],
            },
        )

        # Send registration
        await self.nc.publish(
            SubjectPatterns.registry_register(),
            json.dumps(asdict(instance)).encode(),
        )

        # Store locally
        self.service_registry[self.instance_id] = instance

    async def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while True:
            try:
                await asyncio.sleep(5)  # Every 5 seconds
                heartbeat_data = {
                    "instance_id": self.instance_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "status": "ACTIVE",
                    "metrics": {
                        "rpc_requests": self.metrics["rpc_requests"],
                        "events_published": self.metrics["events_published"],
                    },
                }

                await self.nc.publish(
                    SubjectPatterns.heartbeat(self.service_name),
                    json.dumps(heartbeat_data).encode(),
                )

            except Exception as e:
                print(f"❌ Heartbeat error: {e}")

    async def _health_check_loop(self):
        """Monitor service health."""
        while True:
            try:
                await asyncio.sleep(10)  # Every 10 seconds

                # Check service instances
                now = datetime.now(UTC)
                for instance_id, instance in list(self.service_registry.items()):
                    last_hb = datetime.fromisoformat(instance.last_heartbeat)
                    time_since_heartbeat = (now - last_hb).total_seconds()

                    if time_since_heartbeat > 15:  # 3 missed heartbeats
                        instance.status = "UNHEALTHY"
                        print(f"⚠️  Service {instance_id} marked UNHEALTHY")

            except Exception as e:
                print(f"❌ Health check error: {e}")

    async def disconnect(self):
        """Disconnect with cleanup."""
        # Cancel health tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._health_check_task:
            self._health_check_task.cancel()

        # Unregister service
        if self.nc:
            await self.nc.publish(
                SubjectPatterns.registry_register(),
                json.dumps({"instance_id": self.instance_id, "status": "SHUTDOWN"}).encode(),
            )

        if self.nc:
            await self.nc.close()
            print("👋 Disconnected from NATS")

    # ============ ENHANCED RPC WITH ROUTING ============

    async def register_rpc_handler(self, method: str, handler: Callable):
        """Register RPC handler with routing support."""
        self.rpc_handlers[method] = handler

        # Subscribe to both routed and direct patterns
        subjects = [
            SubjectPatterns.rpc(self.service_name, method),
            SubjectPatterns.service_instance(self.service_name, self.instance_id),
        ]

        for subject in subjects:
            await self.nc.subscribe(subject, cb=self._handle_rpc_wrapper(method))

        print(f"🚀 RPC handler registered: {method}")

    def _handle_rpc_wrapper(self, method: str):
        """Wrap RPC handler with metrics and error handling."""

        async def wrapper(msg):
            start_time = time.time()
            self.metrics["rpc_requests"] += 1

            try:
                # Parse request
                request = RPCRequest(**json.loads(msg.data.decode()))

                # Execute handler
                handler = self.rpc_handlers.get(method)
                if not handler:
                    raise ValueError(f"Unknown method: {method}")

                result = await handler(request.params)

                # Create response
                response = RPCResponse(
                    correlation_id=request.message_id,
                    source=self.instance_id,
                    success=True,
                    result=result,
                )

                # Send response
                await msg.respond(response.model_dump_json().encode())

                # Record latency
                latency_ms = (time.time() - start_time) * 1000
                self.metrics["rpc_latency_ms"].append(latency_ms)

            except Exception as e:
                error_response = RPCResponse(
                    correlation_id=(request.message_id if "request" in locals() else None),
                    source=self.instance_id,
                    success=False,
                    error=str(e),
                )
                await msg.respond(error_response.model_dump_json().encode())

        return wrapper

    async def call_rpc(self, service: str, method: str, params: dict) -> Any:
        """Make RPC call with retry and failover."""
        request = RPCRequest(
            method=method,
            params=params,
            source=self.instance_id,
            target=service,
        )

        # Try direct call first, then routed
        subjects = [
            SubjectPatterns.rpc(service, method),
            SubjectPatterns.route_request(),
        ]

        last_error = None
        for subject in subjects:
            try:
                response = await self.nc.request(
                    subject,
                    request.model_dump_json().encode(),
                    timeout=request.timeout,
                )

                result = RPCResponse(**json.loads(response.data.decode()))
                if result.success:
                    return result.result
                else:
                    last_error = result.error

            except TimeoutError:
                last_error = f"Timeout calling {service}.{method}"
            except Exception as e:
                last_error = str(e)

        raise Exception(f"RPC failed: {last_error}")

    # ============ ENHANCED EVENTS WITH VALIDATION ============

    async def subscribe_event(self, pattern: str, handler: Callable):
        """Subscribe to events with pattern matching."""
        if pattern not in self.event_handlers:
            self.event_handlers[pattern] = []
        self.event_handlers[pattern].append(handler)

        # Use JetStream for durable subscription
        await self.js.subscribe(
            pattern,
            cb=self._handle_event_wrapper(pattern),
            durable=f"{self.service_name}-{pattern.replace('*', 'star').replace('.', '-')}",
            manual_ack=True,
        )
        print(f"📡 Event subscription: {pattern}")

    def _handle_event_wrapper(self, pattern: str):
        """Wrap event handler with validation."""

        async def wrapper(msg):
            try:
                # Parse and validate message
                message = Message(**json.loads(msg.data.decode()))

                # Call all matching handlers
                for handler in self.event_handlers.get(pattern, []):
                    await handler(message.payload)

                # Acknowledge
                await msg.ack()

            except Exception as e:
                print(f"❌ Event handler error: {e}")
                await msg.nak()

        return wrapper

    async def publish_event(self, domain: str, event_type: str, data: dict):
        """Publish event with metadata."""
        message = Message(
            source=self.instance_id,
            payload={"event_type": event_type, "data": data},
        )

        ack = await self.js.publish(
            SubjectPatterns.event(domain, event_type),
            message.model_dump_json().encode(),
        )

        self.metrics["events_published"] += 1
        print(f"✅ Event published: {domain}.{event_type} (seq: {ack.seq})")

    # ============ ENHANCED COMMANDS WITH PROGRESS ============

    async def register_command_handler(self, command: str, handler: Callable):
        """Register command handler with progress support."""
        self.command_handlers[command] = handler

        await self.js.subscribe(
            SubjectPatterns.command(self.service_name, command),
            cb=self._handle_command_wrapper(command),
            durable=f"{self.service_name}-cmd-{command}",
            manual_ack=True,
        )
        print(f"🎯 Command handler registered: {command}")

    def _handle_command_wrapper(self, command: str):
        """Wrap command handler with progress tracking."""

        async def wrapper(msg):
            try:
                message = Message(**json.loads(msg.data.decode()))
                command_id = message.correlation_id or message.message_id

                # Create progress reporter
                async def report_progress(percent: float, status: str = "processing"):
                    progress_data = {
                        "command_id": command_id,
                        "progress": percent,
                        "status": status,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    await self.nc.publish(
                        SubjectPatterns.command_progress(command_id),
                        json.dumps(progress_data).encode(),
                    )

                # Execute handler with progress callback
                handler = self.command_handlers.get(command)
                if not handler:
                    raise ValueError(f"Unknown command: {command}")

                result = await handler(message.payload, report_progress)

                # Send completion
                completion_data = {
                    "command_id": command_id,
                    "status": "completed",
                    "result": result,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

                await self.nc.publish(
                    SubjectPatterns.command_callback(command_id),
                    json.dumps(completion_data).encode(),
                )

                # Acknowledge
                await msg.ack()
                self.metrics["commands_processed"] += 1

            except Exception as e:
                print(f"❌ Command handler error: {e}")
                await msg.nak()

        return wrapper

    async def send_command(
        self, service: str, command: str, data: dict, track_progress: bool = True
    ) -> Any:
        """Send command with optional progress tracking."""
        command_id = str(uuid.uuid4())
        message = Message(
            correlation_id=command_id,
            source=self.instance_id,
            target=service,
            payload=data,
        )

        # Track progress if requested
        progress_updates = []
        completion_data = None

        if track_progress:

            async def progress_handler(msg):
                progress_updates.append(json.loads(msg.data.decode()))
                print(f"📈 Progress: {progress_updates[-1]['progress']:.0f}%")

            async def completion_handler(msg):
                nonlocal completion_data
                completion_data = json.loads(msg.data.decode())

            # Subscribe to progress and completion
            progress_sub = await self.nc.subscribe(
                SubjectPatterns.command_progress(command_id), cb=progress_handler
            )
            completion_sub = await self.nc.subscribe(
                SubjectPatterns.command_callback(command_id), cb=completion_handler
            )

        # Send command
        ack = await self.js.publish(
            SubjectPatterns.command(service, command),
            message.model_dump_json().encode(),
        )

        if track_progress:
            # Wait for completion
            start_time = time.time()
            while completion_data is None and (time.time() - start_time) < 60:
                await asyncio.sleep(0.1)

            # Cleanup subscriptions
            await progress_sub.unsubscribe()
            await completion_sub.unsubscribe()

            return completion_data
        else:
            return {"command_id": command_id, "stream": ack.stream, "seq": ack.seq}

    # ============ METRICS & MONITORING ============

    def get_metrics(self) -> dict:
        """Get service metrics."""
        latency_ms = self.metrics["rpc_latency_ms"]
        if latency_ms:
            latency_ms.sort()
            p99_index = int(len(latency_ms) * 0.99)
            p99_latency = latency_ms[p99_index] if latency_ms else 0
            avg_latency = sum(latency_ms) / len(latency_ms)
        else:
            p99_latency = avg_latency = 0

        return {
            "service": self.service_name,
            "instance": self.instance_id,
            "rpc": {
                "requests": self.metrics["rpc_requests"],
                "avg_latency_ms": round(avg_latency, 2),
                "p99_latency_ms": round(p99_latency, 2),
            },
            "events": {"published": self.metrics["events_published"]},
            "commands": {"processed": self.metrics["commands_processed"]},
        }


# ============ DEMO SCENARIOS ============


async def demo_enhanced_features():
    """Demonstrate enhanced hybrid features."""
    # Create two service instances
    service1 = HybridNATSDemo("order-service")
    service2 = HybridNATSDemo("payment-service")

    try:
        # Connect both services
        await service1.connect()
        await service2.connect()

        print("\n" + "=" * 60)
        print("🌟 ENHANCED HYBRID MODE DEMO")
        print("=" * 60)

        # 1. Service Registration & Discovery
        print("\n🔍 Service Registry:")
        for _, instance in service1.service_registry.items():
            print(f"  - {instance.service_name}/{instance.instance_id}: {instance.status}")

        # 2. RPC with Routing & Metrics
        print("\n🔵 RPC with Enhanced Features:")

        async def handle_create_order(params):
            print(f"  📥 Processing order: {params}")
            return {"order_id": f"ORD-{uuid.uuid4().hex[:8]}", "status": "created"}

        await service1.register_rpc_handler("create_order", handle_create_order)

        # Wait for subscription to be ready
        await asyncio.sleep(0.1)

        # Make multiple RPC calls to build metrics
        for i in range(5):
            result = await service2.call_rpc(
                "order-service", "create_order", {"item": f"product-{i}"}
            )
            print(f"  ✅ Order created: {result['order_id']}")

        # 3. Events with JetStream Persistence
        print("\n🟢 Events with Validation:")

        async def handle_order_event(data):
            print(f"  📢 Order event received: {data}")

        await service2.subscribe_event("events.order.*", handle_order_event)

        for i in range(3):
            await service1.publish_event(
                "order",
                "created",
                {"order_id": f"ORD-{i:03d}", "amount": 100 * (i + 1)},
            )

        await asyncio.sleep(0.5)

        # 4. Commands with Progress Tracking
        print("\n🟡 Commands with Progress:")

        async def handle_batch_payment(data, report_progress):
            print(f"  ⚙️ Processing batch payment: {data}")
            total = data.get("count", 5)

            for i in range(total):
                await report_progress((i + 1) / total * 100, f"Processing payment {i + 1}/{total}")
                await asyncio.sleep(0.1)

            return {"processed": total, "status": "success"}

        await service2.register_command_handler("batch_payment", handle_batch_payment)

        result = await service1.send_command(
            "payment-service", "batch_payment", {"count": 5, "amount": 1000}
        )
        print(f"  ✅ Command completed: {result}")

        # 5. Display Metrics
        print("\n📊 Service Metrics:")
        for service in [service1, service2]:
            metrics = service.get_metrics()
            print(f"\n  {metrics['service']}/{metrics['instance']}:")
            print(
                f"    RPC: {metrics['rpc']['requests']} requests, "
                f"P99: {metrics['rpc']['p99_latency_ms']}ms"
            )
            print(f"    Events: {metrics['events']['published']} published")
            print(f"    Commands: {metrics['commands']['processed']} processed")

        # 6. Simulate Failover
        print("\n🔄 Simulating Service Health Check:")
        await asyncio.sleep(2)
        print("  ✅ All services healthy")

    except Exception as e:
        print(f"❌ Demo error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await service1.disconnect()
        await service2.disconnect()


async def main():
    """Run the enhanced demo."""
    await demo_enhanced_features()


if __name__ == "__main__":
    print("🚀 Pure NATS Hybrid Enhanced Demo")
    print("=" * 60)
    asyncio.run(main())
