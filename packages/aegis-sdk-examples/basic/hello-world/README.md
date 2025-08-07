# Hello World Service

A minimal AegisSDK service demonstrating hexagonal architecture, DDD principles, and TDD methodology.

## Learning Objectives

- Understanding hexagonal (ports & adapters) architecture
- Implementing a basic domain model with Pydantic v2
- Writing tests first (TDD approach)
- Dependency injection and inversion of control
- Service registration and discovery basics

## Architecture

```
hello-world/
├── domain/           # Business logic and entities
│   ├── models.py    # Domain models with Pydantic
│   └── services.py  # Domain services
├── application/      # Use cases and DTOs
│   ├── use_cases.py # Application services
│   └── dtos.py      # Data Transfer Objects
├── infrastructure/   # External adapters
│   ├── adapters.py  # Infrastructure implementations
│   └── config.py    # Configuration
├── ports/           # Interfaces (contracts)
│   ├── inbound.py   # Inbound ports (APIs)
│   └── outbound.py  # Outbound ports (repositories, etc.)
└── tests/           # Comprehensive test suite
    ├── unit/        # Unit tests for each layer
    └── integration/ # Integration tests
```

## Running the Example

### Prerequisites

```bash
pip install aegis-sdk aegis-sdk-dev
```

### Start NATS (using Docker)

```bash
docker run -d --name nats -p 4222:4222 nats:latest
```

### Run the Service

```bash
python main.py
```

### Run Tests

```bash
pytest tests/ -v --cov=.
```

## Key Concepts Demonstrated

1. **Hexagonal Architecture**: Clear separation between business logic and infrastructure
2. **Dependency Inversion**: Ports define contracts, adapters implement them
3. **Test-Driven Development**: Tests written before implementation
4. **Pydantic v2 Validation**: Strict type checking and validation at boundaries
5. **Clean Code**: SOLID principles, small focused functions, meaningful names

## Testing Strategy

- **Unit Tests**: Test each component in isolation with mocks
- **Integration Tests**: Test real interactions with infrastructure
- **Contract Tests**: Verify ports and adapters compatibility
- **TDD Cycle**: Red → Green → Refactor

## Deployment

### Docker

```bash
docker build -t hello-world-service .
docker run -e NATS_URL=nats://host.docker.internal:4222 hello-world-service
```

### Kubernetes

```bash
kubectl apply -f k8s/deployment.yaml
```

## Next Steps

- Explore the `echo-service` example for bidirectional communication
- Check `simple-rpc` for request-response patterns
- Move to intermediate examples for more complex patterns