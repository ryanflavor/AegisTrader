# AegisSDK - Core Trading System SDK

## Overview
AegisSDK is the core SDK package for the AegisTrader automated trading system. It implements Domain-Driven Design (DDD) principles with hexagonal architecture, providing robust microservices infrastructure for financial trading applications.

## Current Status (v0.1.0)
- **Architecture**: Full DDD with hexagonal architecture (Ports & Adapters)
- **Messaging**: NATS JetStream integration for RPC and event streaming
- **High Availability**: Single-active and sticky-active patterns with automatic failover
- **Service Management**: Automatic service registration, discovery, and health monitoring
- **Observability**: Built-in metrics collection and performance monitoring
- **Test Coverage**: ~92% coverage with comprehensive unit and integration tests

## Architecture Layers

### Domain Layer (`domain/`)
Core business logic independent of technical implementation:
- **aggregates.py**: Service and election aggregates (ServiceAggregate, ElectionAggregate)
- **enums.py**: Domain enumerations (ServiceStatus, SubscriptionMode, StickyActiveStatus, etc.)
- **events.py**: Domain events (ServiceRegistered, ServiceHealthUpdated, etc.)
- **exceptions.py**: Domain-specific exceptions hierarchy
- **models.py**: Core entities (ServiceInfo, ServiceHealth, ElectionInfo)
- **metrics_models.py**: Metrics domain models (MetricsSnapshot, MetricsSummaryData)
- **patterns.py**: NATS subject patterns for routing
- **services.py**: Domain services (MessageRoutingService, HealthCheckService, StickyActiveElectionService)
- **types.py**: Type definitions and aliases
- **value_objects.py**: Immutable value objects (ServiceName, InstanceId, RetryPolicy, FailoverPolicy, etc.)

### Application Layer (`application/`)
Orchestrates domain logic and coordinates use cases:
- **service.py**: Base Service class with lifecycle management, handler registry, and health checks
- **single_active_service.py**: Single-active instance pattern implementation
- **single_active_dtos.py**: Data transfer objects for single-active configuration
- **sticky_active_use_cases.py**: Sticky-active pattern use cases (election, failover)
- **failover_monitoring_use_case.py**: Automatic failover monitoring and coordination
- **use_cases.py**: Core application use cases (RegisterService, DiscoverServices, etc.)
- **metrics.py**: Application-level metrics collection
- **dependency_provider.py**: Dependency injection container

### Infrastructure Layer (`infrastructure/`)
Technical implementations of ports:
- **nats_adapter.py**: NATS messaging implementation with connection management
- **nats_kv_store.py**: NATS KV store implementation for distributed state
- **nats_kv_election_repository.py**: Leader election using NATS KV
- **kv_service_registry.py**: Service registry using key-value storage
- **basic_service_discovery.py**: Simple service discovery implementation
- **cached_service_discovery.py**: Service discovery with caching
- **watchable_cached_service_discovery.py**: Real-time service discovery with watchers
- **election_coordinator.py**: Coordinates leader election process
- **heartbeat_monitor.py**: Monitors service heartbeats for health
- **in_memory_repository.py**: In-memory service repository for testing
- **in_memory_metrics.py**: In-memory metrics collection
- **simple_logger.py**: Basic logging implementation
- **system_clock.py**: System clock implementation
- **config.py**: Configuration management
- **bootstrap.py**: SDK initialization and dependency setup
- **factories.py**: Factory implementations for creating components
- **application_factories.py**: Application-specific factories
- **key_sanitizer.py**: Sanitizes keys for NATS KV storage
- **serialization.py**: JSON serialization utilities

### Ports Layer (`ports/`)
Interface definitions for dependency inversion:
- **message_bus.py**: Message bus abstraction (MessageBusPort)
- **repository.py**: Service repository interface
- **service_discovery.py**: Service discovery interface
- **service_registry.py**: Service registry interface
- **election_repository.py**: Election repository for leader election
- **kv_store.py**: Key-value store abstraction
- **metrics.py**: Metrics collection interface
- **logger.py**: Logging abstraction
- **clock.py**: Clock abstraction for time operations
- **factory_ports.py**: Factory interfaces (ElectionRepositoryFactory, KVStoreFactory, UseCaseFactory)

## Key Features

### 1. Service Management
- Automatic service registration with heartbeats
- Dynamic service discovery with multiple strategies (round-robin, random, least-loaded)
- Health monitoring and automatic deregistration of unhealthy services
- Service metadata and capability advertisement

### 2. High Availability Patterns
- **Single-Active Pattern**: Only one instance processes requests, with automatic failover
- **Sticky-Active Pattern**: Client connections stick to active instance with retry on failure
- **Leader Election**: Distributed leader election using NATS KV
- **Failover Policies**: Aggressive (<2s), Balanced (2-5s), Conservative (5-10s)

### 3. Communication Patterns
- **RPC**: Request-response pattern with timeout handling
- **Events**: Pub/sub with domain-based routing
- **Streaming**: Durable message streams with acknowledgment
- **Broadcast**: One-to-many communication

### 4. Observability
- Built-in metrics collection (request count, latency, errors)
- Performance monitoring and reporting
- Health check endpoints
- Comprehensive logging with context

### 5. Resilience
- Automatic reconnection to NATS
- Retry policies with exponential backoff
- Circuit breaker pattern support
- Graceful degradation on service failure

## Examples

### Basic Service
```python
from aegis_sdk.application.service import Service, ServiceConfig

config = ServiceConfig(
    name="my-service",
    version="1.0.0",
    nats_url="nats://localhost:4222"
)

service = Service(config)
await service.start()
```

### Single-Active Service with Failover
```python
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.domain.value_objects import FailoverPolicy

service = SingleActiveService(
    config=config,
    failover_policy=FailoverPolicy.aggressive()  # <2 second failover
)
await service.start()
```

### Service Discovery
```python
from aegis_sdk.application.use_cases import DiscoverServicesUseCase

discover = DiscoverServicesUseCase(discovery_service)
services = await discover.execute(service_name="pricing-service")
```

## Testing
- **Unit Tests**: Comprehensive coverage of all layers
- **Integration Tests**: NATS integration, failover scenarios, K8s deployment
- **Test Utilities**: Mocks, fixtures, and test helpers
- **Coverage**: ~92% code coverage

Run tests:
```bash
cd packages/aegis-sdk
uv run pytest
uv run pytest --cov=aegis_sdk --cov-report=term-missing
```

## Dependencies
- Python 3.11+
- nats-py: NATS client library
- pydantic v2: Data validation and settings
- asyncio: Asynchronous programming

## Service Patterns

AegisSDK provides two fundamental service patterns:

1. **Load-Balanced Service** (`Service`)
   - Multiple instances handle requests concurrently
   - Automatic load distribution via NATS

2. **Single-Active Pattern** (`SingleActiveService`)
   - Only leader instance processes exclusive requests
   - Sticky behavior through client retry configuration
   
Note: There is no separate `StickyActiveService` class. The "sticky" 
behavior is achieved by configuring client-side retry policies when
calling SingleActiveService instances that return NOT_ACTIVE errors.

## Usage in AegisTrader
This SDK provides the foundation for all AegisTrader microservices:
- Trading services (Order, Pricing, Risk)
- Monitoring services (API, UI)
- Market data services
- Strategy execution services
