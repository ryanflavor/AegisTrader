# AegisSDK - Comprehensive Project Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [API Reference](#api-reference)
5. [Usage Patterns](#usage-patterns)
6. [Installation & Setup](#installation--setup)
7. [Examples](#examples)
8. [Best Practices](#best-practices)
9. [Advanced Features](#advanced-features)
10. [Troubleshooting](#troubleshooting)

---

## Overview

AegisSDK is a lightweight Inter-Process Communication (IPC) SDK built on pure NATS, following hexagonal architecture and Domain-Driven Design (DDD) principles. It provides minimal abstraction over NATS while offering essential features for building distributed microservices.

### Key Features

- **Minimal**: ~500 lines total vs 25,000+ in full frameworks
- **Fast**: Sub-millisecond latency with pure NATS
- **Simple**: Decorator-based API for services
- **Flexible**: Hexagonal architecture allows swapping implementations
- **Reliable**: Built-in service discovery, heartbeats, and failover
- **Observable**: Comprehensive metrics and tracing support

### Design Principles

1. **Hexagonal Architecture**: Core domain isolated from infrastructure
2. **Domain-Driven Design**: Models and patterns reflect business concepts
3. **Minimal Abstraction**: Only essential features, leveraging NATS capabilities
4. **Performance First**: Direct NATS usage for minimal overhead

---

## Architecture

### High-Level Architecture

The SDK follows a clean, layered architecture:

```
┌─────────────────────────────────────────────┐
│            Infrastructure Layer             │
│  • NATS Adapter (messaging)                │
│  • KV Store Adapter (persistence)          │
│  • Service Discovery (environment)         │
│  • Logging, Metrics, Clock                 │
└─────────────────▲───────────────────────────┘
                  │ implements
┌─────────────────▼───────────────────────────┐
│              Ports Layer                    │
│  • MessageBusPort (interface)              │
│  • ServiceRegistryPort (interface)         │
│  • ServiceDiscoveryPort (interface)        │
│  • KVStorePort (interface)                 │
└─────────────────▲───────────────────────────┘
                  │ uses
┌─────────────────▼───────────────────────────┐
│           Application Layer                 │
│  • Service (main service class)            │
│  • Use Cases (business operations)         │
│  • DTOs (data transfer objects)            │
│  • Dependency Injection                    │
└─────────────────▲───────────────────────────┘
                  │ orchestrates
┌─────────────────▼───────────────────────────┐
│             Domain Layer                    │
│  • Models (Message, Event, Command, RPC)   │
│  • Value Objects (ServiceName, InstanceId) │
│  • Enums (ServiceStatus, CommandPriority)  │
│  • Patterns (Subject naming patterns)      │
│  • Domain Events & Services                │
└─────────────────────────────────────────────┘
```

### Communication Patterns

#### 1. RPC (Request-Response)
- **Purpose**: Synchronous service-to-service calls
- **Implementation**: NATS request-reply pattern
- **Load Balancing**: Automatic via queue groups
- **Subject Pattern**: `rpc.{service}.{method}`

#### 2. Event Publishing
- **Purpose**: Asynchronous event notification
- **Implementation**: NATS JetStream for reliability
- **Features**: Durable subscriptions, wildcard patterns
- **Subject Pattern**: `events.{domain}.{event_type}`

#### 3. Command Processing
- **Purpose**: Long-running async operations
- **Implementation**: JetStream work queues
- **Features**: Progress tracking, priority-based execution
- **Subject Pattern**: `commands.{service}.{command}`

#### 4. Service Registration
- **Purpose**: Service discovery and health tracking
- **Implementation**: NATS KV Store
- **Features**: TTL-based expiration, heartbeats
- **Subject Pattern**: `service.{name}.{operation}`

---

## Core Components

### 1. Service Class

The main service abstraction following hexagonal architecture:

```python
from aegis_sdk import Service, NATSAdapter

# Initialize with dependency injection
bus = NATSAdapter()
await bus.connect(["nats://localhost:4222"])

service = Service(
    service_name="order-service",
    message_bus=bus,
    service_registry=registry,    # Optional
    service_discovery=discovery,  # Optional
    logger=logger                 # Optional
)
```

### 2. Domain Models

#### Message (Base Class)
```python
class Message(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str | None = None
    target: str | None = None
```

#### RPCRequest & RPCResponse
```python
class RPCRequest(Message):
    method: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    timeout: float = Field(default=5.0, gt=0)

class RPCResponse(Message):
    success: bool = Field(default=True)
    result: Any | None = None
    error: str | None = None
```

#### Event
```python
class Event(Message):
    domain: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    version: str = Field(default="1.0")
```

#### Command
```python
class Command(Message):
    command: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: str = Field(default=CommandPriority.NORMAL.value)
    max_retries: int = Field(default=3, ge=0)
    timeout: float = Field(default=300.0, gt=0)
```

### 3. Port Interfaces

#### MessageBusPort
```python
class MessageBusPort(ABC):
    @abstractmethod
    async def connect(self, servers: list[str]) -> None: ...

    @abstractmethod
    async def call_rpc(self, request: RPCRequest) -> RPCResponse: ...

    @abstractmethod
    async def publish_event(self, event: Event) -> None: ...

    @abstractmethod
    async def send_command(self, command: Command, track_progress: bool = True) -> dict[str, Any]: ...
```

#### ServiceDiscoveryPort
```python
class ServiceDiscoveryPort(ABC):
    @abstractmethod
    async def discover_instances(self, service_name: str, only_healthy: bool = True) -> list[ServiceInstance]: ...

    @abstractmethod
    async def select_instance(
        self,
        service_name: str,
        strategy: SelectionStrategy = SelectionStrategy.ROUND_ROBIN
    ) -> ServiceInstance | None: ...
```

#### KVStorePort
```python
class KVStorePort(ABC):
    @abstractmethod
    async def get(self, key: str) -> KVEntry | None: ...

    @abstractmethod
    async def put(self, key: str, value: Any, options: KVOptions | None = None) -> int: ...

    @abstractmethod
    async def watch(self, key: str | None = None, prefix: str | None = None) -> AsyncIterator[KVWatchEvent]: ...
```

---

## API Reference

### Service Lifecycle

```python
# Initialize service
service = Service("my-service", message_bus)

# Lifecycle hooks
async def on_start(self) -> None:
    """Called during service startup"""
    pass

async def on_stop(self) -> None:
    """Called during service shutdown"""
    pass

# Start/stop service
await service.start()
await service.stop()
```

### RPC Methods

```python
# Register RPC handler (decorator)
@service.rpc("create_order")
async def create_order(params: dict) -> dict:
    order_id = params["order_id"]
    # Business logic here
    return {"order_id": order_id, "status": "created"}

# Call RPC method
request = service.create_rpc_request(
    service="order-service",
    method="create_order",
    params={"order_id": "123", "amount": 100},
    timeout=10.0
)
result = await service.call_rpc(request)
```

### Event Handling

```python
# Subscribe to events (decorator)
@service.subscribe("payment.*", mode=SubscriptionMode.COMPETE)
async def handle_payment_event(event: Event):
    print(f"Payment event: {event.event_type}")
    print(f"Payload: {event.payload}")

# Publish events
event = service.create_event(
    domain="order",
    event_type="created",
    payload={"order_id": "123", "amount": 100}
)
await service.publish_event(event)
```

### Command Processing

```python
# Register command handler (decorator)
@service.command("process_batch")
async def process_batch(command: Command, progress_callback):
    total = command.payload.get("total", 100)
    for i in range(total):
        # Process item
        await progress_callback(i * 100 / total, f"Processed {i+1}/{total}")
        await asyncio.sleep(0.1)
    return {"processed": total, "status": "completed"}

# Send command
command = service.create_command(
    service="worker-service",
    command_name="process_batch",
    payload={"total": 50},
    priority=CommandPriority.HIGH
)
result = await service.send_command(command)
```

### Service Discovery

```python
# Discover service instances
discovery = CachedServiceDiscovery(kv_store)
instances = await discovery.discover_instances("order-service")

# Select instance with strategy
instance = await discovery.select_instance(
    "order-service",
    strategy=SelectionStrategy.ROUND_ROBIN
)

# Invalidate cache on failure
await discovery.invalidate_cache("order-service")
```

### KV Store Operations

```python
kv = NATSKVStore(nats_adapter)
await kv.connect("my-bucket")

# Basic operations
await kv.put("user:123", {"name": "John", "email": "john@example.com"})
entry = await kv.get("user:123")

# Batch operations
users = {
    "user:124": {"name": "Jane", "email": "jane@example.com"},
    "user:125": {"name": "Bob", "email": "bob@example.com"}
}
revisions = await kv.put_many(users)

# Watch for changes
async for event in kv.watch(prefix="user:"):
    print(f"Operation: {event.operation}, Key: {event.entry.key}")
```

---

## Usage Patterns

### Pattern 1: Simple Load-Balanced Service

```python
import asyncio
from aegis_sdk import Service, NATSAdapter

async def main():
    # Setup
    bus = NATSAdapter()
    await bus.connect(["nats://localhost:4222"])

    service = Service("calculator", bus)

    # RPC handler
    @service.rpc("add")
    async def add(params: dict) -> dict:
        a = params.get("a", 0)
        b = params.get("b", 0)
        return {"result": a + b}

    # Event handler
    @service.subscribe("math.*")
    async def handle_math_event(event):
        print(f"Math event: {event.event_type} - {event.payload}")

    # Start service
    await service.start()

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await service.stop()
        await bus.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### Pattern 2: Single-Active Service with Failover

```python
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.domain.value_objects import FailoverPolicy

async def main():
    # Single-active service with fast failover
    service = SingleActiveService(
        name="critical-processor",
        message_bus=bus,
        failover_policy=FailoverPolicy.aggressive()  # <2s failover
    )

    @service.rpc("process_critical_task")
    async def process_task(params: dict) -> dict:
        # Only the leader processes this
        if not service.is_leader():
            raise Exception("NOT_ACTIVE")

        # Critical processing logic
        return {"status": "processed", "instance": service.instance_id}

    await service.start()
    await asyncio.Event().wait()
```

### Pattern 3: Event-Driven Microservice

```python
async def main():
    service = Service("notification-service", bus)

    # Handle different event types
    @service.subscribe("user.registered")
    async def send_welcome_email(event):
        user_data = event.payload
        # Send welcome email logic
        await send_email(user_data["email"], "Welcome!")

    @service.subscribe("order.completed")
    async def send_order_confirmation(event):
        order_data = event.payload
        # Send order confirmation logic
        await send_sms(order_data["phone"], "Order confirmed!")

    # Publish metrics events
    @service.subscribe("system.metrics")
    async def handle_metrics(event):
        metrics = event.payload
        # Process and store metrics
        await store_metrics(metrics)

    await service.start()
    await asyncio.Event().wait()
```

### Pattern 4: Command Processor with Progress Tracking

```python
async def main():
    service = Service("batch-processor", bus)

    @service.command("process_large_dataset")
    async def process_dataset(command: Command, progress):
        dataset_url = command.payload["dataset_url"]
        batch_size = command.payload.get("batch_size", 1000)

        # Download dataset
        await progress(10, "Downloading dataset...")
        data = await download_dataset(dataset_url)

        # Process in batches
        total_items = len(data)
        for i in range(0, total_items, batch_size):
            batch = data[i:i+batch_size]
            await process_batch(batch)

            percent = min(90, 10 + (i * 80 / total_items))
            await progress(percent, f"Processed {i+len(batch)}/{total_items} items")

        # Finalize
        await progress(100, "Processing complete")
        return {"processed_items": total_items, "status": "success"}

    await service.start()
    await asyncio.Event().wait()
```

---

## Installation & Setup

### Prerequisites

- Python 3.13+
- NATS server (2.9+ for JetStream)
- Docker (optional, for containerized NATS)

### Installation

```bash
# From PyPI (when published)
pip install aegis-sdk

# From source
git clone https://github.com/your-org/aegis-trader.git
cd aegis-trader/packages/aegis-sdk
pip install -e .
```

### NATS Server Setup

#### Option 1: Docker Compose
```yaml
version: '3.8'
services:
  nats:
    image: nats:2.10-alpine
    ports:
      - "4222:4222"
      - "8222:8222"
    command:
      - "--jetstream"
      - "--store_dir=/data"
      - "--http_port=8222"
    volumes:
      - nats-data:/data

volumes:
  nats-data:
```

#### Option 2: Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nats
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nats
  template:
    metadata:
      labels:
        app: nats
    spec:
      containers:
      - name: nats
        image: nats:2.10-alpine
        args:
        - "--jetstream"
        - "--store_dir=/data"
        ports:
        - containerPort: 4222
        - containerPort: 8222
        volumeMounts:
        - name: nats-storage
          mountPath: /data
      volumes:
      - name: nats-storage
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: nats
spec:
  selector:
    app: nats
  ports:
  - name: client
    port: 4222
    targetPort: 4222
  - name: monitor
    port: 8222
    targetPort: 8222
```

### Environment Configuration

```python
# Configuration with environment variables
from aegis_sdk.infrastructure.config import NATSConnectionConfig

config = NATSConnectionConfig(
    servers=["nats://localhost:4222"],
    enable_jetstream=True,
    pool_size=2,
    service_name="my-service",
    instance_id="instance-1"
)

adapter = NATSAdapter(config)
```

### Quick Setup Script

```bash
#!/bin/bash
# setup_dev_environment.sh

# Start NATS with JetStream
docker run -d --name nats \
  -p 4222:4222 -p 8222:8222 \
  nats:2.10-alpine \
  --jetstream --store_dir=/data --http_port=8222

# Wait for NATS to be ready
echo "Waiting for NATS to start..."
sleep 5

# Verify connection
nats --server=localhost:4222 server info

echo "✅ NATS is ready at localhost:4222"
echo "📊 Monitor at http://localhost:8222"
```

---

## Examples

### Example 1: Echo Service

```python
# echo_service.py
import asyncio
from aegis_sdk import Service, NATSAdapter

async def main():
    # Setup
    adapter = NATSAdapter()
    await adapter.connect(["nats://localhost:4222"])

    service = Service("echo-service", adapter)

    # Simple echo RPC
    @service.rpc("echo")
    async def echo(params: dict) -> dict:
        message = params.get("message", "")
        return {
            "echo": message,
            "timestamp": "2024-01-01T00:00:00Z",
            "instance": service.instance_id
        }

    # Echo event handler
    @service.subscribe("test.*")
    async def handle_test_event(event):
        print(f"Received test event: {event.event_type}")
        # Echo back as new event
        echo_event = service.create_event(
            domain="echo",
            event_type="response",
            payload={"original": event.payload}
        )
        await service.publish_event(echo_event)

    await service.start()
    print(f"Echo service started: {service.instance_id}")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await service.stop()
        await adapter.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 2: Client Application

```python
# client.py
import asyncio
from aegis_sdk import Service, NATSAdapter

async def main():
    # Setup client
    adapter = NATSAdapter()
    await adapter.connect(["nats://localhost:4222"])

    client = Service("test-client", adapter)
    await client.start()

    try:
        # Test RPC call
        request = client.create_rpc_request(
            service="echo-service",
            method="echo",
            params={"message": "Hello, AegisSDK!"}
        )
        response = await client.call_rpc(request)
        print(f"RPC Response: {response}")

        # Test event publishing
        event = client.create_event(
            domain="test",
            event_type="ping",
            payload={"sender": client.instance_id}
        )
        await client.publish_event(event)
        print("Event published")

        # Wait a bit to see responses
        await asyncio.sleep(2)

    finally:
        await client.stop()
        await adapter.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 3: KV Store Usage

```python
# kv_example.py
import asyncio
from aegis_sdk.infrastructure import NATSAdapter, NATSKVStore
from aegis_sdk.domain.models import KVOptions

async def main():
    # Setup
    adapter = NATSAdapter()
    await adapter.connect(["nats://localhost:4222"])

    kv = NATSKVStore(adapter)
    await kv.connect("user-data")

    try:
        # Store user data
        user = {
            "name": "John Doe",
            "email": "john@example.com",
            "role": "admin"
        }
        revision = await kv.put("user:123", user)
        print(f"Stored user with revision: {revision}")

        # Retrieve user data
        entry = await kv.get("user:123")
        if entry:
            print(f"Retrieved: {entry.value}")
            print(f"Revision: {entry.revision}")

        # Update with revision check
        updated_user = {**user, "last_login": "2024-01-01T12:00:00Z"}
        options = KVOptions(revision=revision)
        new_revision = await kv.put("user:123", updated_user, options)
        print(f"Updated to revision: {new_revision}")

        # Watch for changes
        print("Watching for changes...")

        async def watch_changes():
            count = 0
            async for event in kv.watch(prefix="user:"):
                print(f"Change detected: {event.operation}")
                if event.entry:
                    print(f"  Key: {event.entry.key}")
                    print(f"  Value: {event.entry.value}")
                count += 1
                if count >= 3:
                    break

        # Start watching in background
        watch_task = asyncio.create_task(watch_changes())

        # Make some changes
        await asyncio.sleep(0.1)
        await kv.put("user:124", {"name": "Jane Doe"})
        await asyncio.sleep(0.1)
        await kv.put("user:125", {"name": "Bob Smith"})
        await asyncio.sleep(0.1)
        await kv.delete("user:125")

        # Wait for watcher to complete
        await watch_task

    finally:
        await kv.disconnect()
        await adapter.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Best Practices

### 1. Service Design

- **Single Responsibility**: Each service should have one clear purpose
- **Stateless Design**: Prefer stateless services for better scalability
- **Error Handling**: Always handle errors gracefully and return meaningful error messages
- **Validation**: Validate all input parameters using Pydantic models

```python
@service.rpc("create_user")
async def create_user(params: dict) -> dict:
    # Validate input
    try:
        user_data = UserCreateRequest(**params)
    except ValidationError as e:
        raise ValueError(f"Invalid input: {e}")

    # Business logic with error handling
    try:
        user_id = await user_repository.create(user_data)
        return {"user_id": user_id, "status": "created"}
    except DuplicateEmailError:
        raise ValueError("Email already exists")
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise RuntimeError("Internal server error")
```

### 2. Event Design

- **Domain Events**: Events should represent business events, not technical events
- **Immutable Payload**: Event payloads should be immutable and complete
- **Versioning**: Always include version information for event schema evolution

```python
# Good: Business event
@service.subscribe("order.payment_completed")
async def handle_payment_completed(event):
    order_id = event.payload["order_id"]
    amount = event.payload["amount"]
    await fulfill_order(order_id)

# Bad: Technical event
@service.subscribe("database.row_updated")
async def handle_db_update(event):
    # Too technical, unclear business meaning
    pass
```

### 3. Error Handling

- **Structured Errors**: Use structured error responses
- **Retry Logic**: Implement retry logic for transient failures
- **Circuit Breaker**: Use circuit breaker pattern for external dependencies

```python
from aegis_sdk.domain.exceptions import ServiceUnavailableError

async def call_external_service(request):
    max_retries = 3
    backoff = 1

    for attempt in range(max_retries):
        try:
            response = await service.call_rpc(request)
            return response
        except ServiceUnavailableError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(backoff * (2 ** attempt))
```

### 4. Configuration Management

- **Environment Variables**: Use environment variables for configuration
- **Configuration Validation**: Validate configuration at startup
- **Secrets Management**: Never hardcode secrets

```python
import os
from aegis_sdk.infrastructure.config import NATSConnectionConfig

config = NATSConnectionConfig(
    servers=os.getenv("NATS_SERVERS", "nats://localhost:4222").split(","),
    username=os.getenv("NATS_USERNAME"),
    password=os.getenv("NATS_PASSWORD"),
    enable_jetstream=os.getenv("ENABLE_JETSTREAM", "true").lower() == "true"
)
```

### 5. Testing

- **Unit Tests**: Test business logic in isolation
- **Integration Tests**: Test service interactions
- **Contract Tests**: Verify API contracts

```python
import pytest
from unittest.mock import AsyncMock
from aegis_sdk.testing import MockMessageBus

@pytest.fixture
async def service():
    mock_bus = MockMessageBus()
    service = Service("test-service", mock_bus)
    await service.start()
    yield service
    await service.stop()

@pytest.mark.asyncio
async def test_create_user_rpc(service):
    # Arrange
    params = {"name": "John Doe", "email": "john@example.com"}

    # Act
    result = await service._handler_registry.rpc_handlers["create_user"](params)

    # Assert
    assert result["status"] == "created"
    assert "user_id" in result
```

### 6. Monitoring and Observability

- **Structured Logging**: Use structured logging with correlation IDs
- **Metrics**: Collect business and technical metrics
- **Tracing**: Implement distributed tracing

```python
import structlog
from aegis_sdk.infrastructure.simple_logger import StructuredLogger

logger = StructuredLogger()

@service.rpc("process_order")
async def process_order(params: dict) -> dict:
    order_id = params["order_id"]

    with logger.context(order_id=order_id, operation="process_order"):
        logger.info("Starting order processing")

        try:
            result = await business_logic.process_order(order_id)
            logger.info("Order processed successfully", result=result)
            return result
        except Exception as e:
            logger.error("Order processing failed", error=str(e))
            raise
```

---

## Advanced Features

### 1. Single-Active Services

For services that need leader election and failover:

```python
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.domain.value_objects import FailoverPolicy

service = SingleActiveService(
    name="payment-processor",
    failover_policy=FailoverPolicy(
        election_timeout=2.0,     # Time to declare leader dead
        heartbeat_interval=0.5,   # Heartbeat frequency
        retry_interval=0.1        # Election retry interval
    )
)

@service.rpc("process_payment")
async def process_payment(params: dict) -> dict:
    # Only leader processes payments
    if not service.is_leader():
        raise ServiceUnavailableError("Service not active")

    # Process payment
    return await payment_gateway.charge(params)
```

### 2. Service Discovery

Automatic service discovery with health checking:

```python
from aegis_sdk.infrastructure.cached_service_discovery import CachedServiceDiscovery
from aegis_sdk.ports.service_discovery import SelectionStrategy

discovery = CachedServiceDiscovery(kv_store, cache_ttl=30.0)

# Discover healthy instances
instances = await discovery.discover_instances("payment-service")

# Select instance with strategy
instance = await discovery.select_instance(
    "payment-service",
    strategy=SelectionStrategy.ROUND_ROBIN
)

# Use selected instance
if instance:
    request.target = instance.instance_id
    response = await service.call_rpc(request)
```

### 3. Event Streaming

Stream processing with JetStream:

```python
@service.subscribe("orders.*", mode=SubscriptionMode.BROADCAST)
async def track_order_analytics(event):
    """All instances process for analytics"""
    await analytics.track_event(event)

@service.subscribe("orders.*", mode=SubscriptionMode.COMPETE)
async def process_order_fulfillment(event):
    """Only one instance processes for fulfillment"""
    if event.event_type == "order.created":
        await fulfillment.process_order(event.payload)
```

### 4. Custom Serialization

Support for MessagePack and custom serializers:

```python
from aegis_sdk.infrastructure.config import NATSConnectionConfig

config = NATSConnectionConfig(
    use_msgpack=True  # Use MessagePack for better performance
)

adapter = NATSAdapter(config)
```

### 5. Metrics and Monitoring

Built-in metrics collection:

```python
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics

metrics = InMemoryMetrics()
adapter = NATSAdapter(metrics=metrics)

# Metrics are automatically collected
# Access via metrics.get_all()
snapshot = metrics.get_all()
print(f"RPC calls: {snapshot.counters.get('rpc.calls', 0)}")
print(f"Average latency: {snapshot.summaries.get('rpc.latency.avg', 0)}")
```

---

## Troubleshooting

### Common Issues

#### 1. Connection Refused
```
Error: [Errno 61] Connection refused
```

**Solution**: Ensure NATS server is running
```bash
# Check if NATS is running
docker ps | grep nats

# Start NATS if not running
docker run -d --name nats -p 4222:4222 nats:2.10-alpine --jetstream
```

#### 2. JetStream Not Enabled
```
Error: JetStream not enabled
```

**Solution**: Start NATS with JetStream enabled
```bash
docker run -d --name nats -p 4222:4222 nats:2.10-alpine --jetstream --store_dir=/data
```

#### 3. Service Not Found
```
Error: ServiceUnavailableError: payment-service
```

**Solution**: Check service registration
```bash
# List registered services
nats kv ls
nats kv get service_registry payment-service
```

#### 4. RPC Timeout
```
Error: Timeout calling service.method
```

**Solution**: Check service health and increase timeout
```python
request = service.create_rpc_request(
    service="slow-service",
    method="heavy_operation",
    timeout=30.0  # Increase timeout
)
```

#### 5. Event Not Delivered
```
Events published but not received by subscribers
```

**Solution**: Check JetStream streams and consumer configuration
```bash
# List streams
nats stream ls

# Check consumer info
nats consumer info EVENTS
```

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use structured logging
from aegis_sdk.infrastructure.simple_logger import StructuredLogger
logger = StructuredLogger(level="DEBUG")
```

### Health Checks

Implement health check endpoints:

```python
@service.rpc("health")
async def health_check(params: dict) -> dict:
    return {
        "status": "healthy",
        "instance_id": service.instance_id,
        "uptime": service.uptime_seconds(),
        "is_leader": getattr(service, 'is_leader', lambda: None)()
    }
```

### Performance Monitoring

Monitor key metrics:

```python
@service.rpc("metrics")
async def get_metrics(params: dict) -> dict:
    snapshot = metrics.get_all()
    return {
        "counters": snapshot.counters,
        "gauges": snapshot.gauges,
        "summaries": snapshot.summaries,
        "uptime": snapshot.uptime_seconds
    }
```

---

## Performance Characteristics

### Latency Benchmarks
- **RPC**: < 1ms (p99) for same-datacenter calls
- **Events**: 1-2ms with JetStream persistence
- **Commands**: 2-5ms with progress tracking

### Throughput Benchmarks
- **RPC**: 10,000+ req/s per service instance
- **Events**: 50,000+ events/s publish rate
- **Commands**: 1,000+ concurrent operations

### Resource Usage
- **Memory**: ~50MB per service instance
- **CPU**: < 5% idle, scales linearly with load
- **Connections**: 2-10 NATS connections per service

### Comparison with Full Frameworks

| Feature | AegisSDK | Full IPC Framework |
|---------|----------|-------------------|
| Lines of Code | ~500 | 25,000+ |
| Core Dependencies | 3 | 15+ |
| RPC Latency | <1ms | 5-10ms |
| Memory Footprint | ~50MB | 200MB+ |
| Learning Curve | 1 day | 1-2 weeks |
| Features | Essential IPC | Everything |
| Configuration | Minimal | Extensive |
| Production Ready | Yes | Yes |

---

This comprehensive documentation provides everything needed to understand, implement, and operate services using the AegisSDK. The SDK's focus on simplicity, performance, and clean architecture makes it an excellent choice for building distributed microservices with minimal overhead.
