# aegis-sdk

## Overview
This is the core SDK package for the AegisTrader system, implementing Domain-Driven Design (DDD) principles with clean architecture patterns.

## Architecture
The SDK follows a hexagonal architecture with clear separation of concerns:

- **domain/**: Core business logic and domain models
  - `aggregates.py`: Domain aggregates and aggregate roots
  - `events.py`: Domain events
  - `models.py`: Domain entities and models
  - `value_objects.py`: Value objects
  - `services.py`: Domain services
  - `patterns.py`: Domain patterns and interfaces
  - `exceptions.py`: Domain-specific exceptions
  - `metrics_models.py`: Metrics-related domain models

- **application/**: Application services and use cases
  - `service.py`: Application services
  - `single_active_service.py`: Single active instance service pattern
  - `use_cases.py`: Application use cases
  - `metrics.py`: Application-level metrics

- **infrastructure/**: Technical implementations
  - `nats_adapter.py`: NATS messaging adapter
  - `kv_service_registry.py`: Key-value based service registry
  - `service_discovery.py`: Service discovery implementations
  - `in_memory_repository.py`: In-memory repository implementation
  - `config.py`: Configuration management
  - `factories.py`: Factory classes for creating infrastructure components

- **ports/**: Interface definitions (adapters pattern)
  - `message_bus.py`: Message bus interface
  - `repository.py`: Repository interface
  - `service_discovery.py`: Service discovery interface
  - `metrics.py`: Metrics interface
  - `logger.py`: Logger interface
  - `clock.py`: Clock abstraction interface

## Key Design Patterns
- Domain-Driven Design (DDD)
- Hexagonal Architecture (Ports & Adapters)
- Repository Pattern
- Event-Driven Architecture
- Dependency Injection

## Testing
When modifying this SDK, ensure all tests pass and maintain high test coverage.

## Usage
This SDK is used as the foundation for all AegisTrader services and applications.
