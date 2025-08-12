# Echo Service DDD Example

A comprehensive example service demonstrating Domain-Driven Design (DDD) principles with hexagonal architecture using the AegisSDK framework. This service was created using `aegis-sdk-dev` bootstrap tools and serves as a reference implementation for building microservices with clean architecture.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Service](#running-the-service)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Development Notes](#development-notes)
- [Known Issues](#known-issues)

## Overview

The Echo Service DDD is a demonstration microservice that processes echo requests in various modes (simple, reverse, uppercase, delayed, transform, batch) while showcasing proper DDD implementation patterns. It integrates with the AegisSDK for service discovery, health monitoring, and distributed messaging via NATS.

### Key Characteristics

- **Domain-Driven Design**: Clear separation of domain, application, and infrastructure concerns
- **Hexagonal Architecture**: Ports and adapters pattern for external dependencies
- **Test-Driven Development**: Comprehensive test coverage following TDD principles
- **Cloud-Native**: Kubernetes-ready with Helm charts and health checks
- **Observable**: Built-in metrics, health monitoring, and structured logging

## Architecture

### Layered Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│                   (RPC/HTTP Endpoints)                   │
├─────────────────────────────────────────────────────────┤
│                   Application Layer                      │
│         (Use Cases, Command/Query Handlers)             │
├─────────────────────────────────────────────────────────┤
│                     Domain Layer                         │
│      (Entities, Value Objects, Domain Services)         │
├─────────────────────────────────────────────────────────┤
│                  Infrastructure Layer                    │
│           (Adapters, External Services)                 │
└─────────────────────────────────────────────────────────┘
```

### Directory Structure

```
echo-service-ddd/
├── domain/                 # Core business logic
│   ├── entities.py        # Domain entities (EchoRequest, EchoResponse)
│   ├── value_objects.py   # Value objects (EchoMode, MessagePriority)
│   ├── services.py        # Domain services (EchoProcessor, MetricsCollector)
│   ├── repositories.py    # Repository interfaces
│   └── events.py          # Domain events
├── application/           # Application services
│   ├── use_cases.py      # Business use cases
│   ├── commands.py       # Command objects
│   ├── queries.py        # Query objects
│   ├── handlers.py       # Command/Query handlers
│   └── dto.py            # Data transfer objects
├── infra/                # Infrastructure implementations
│   ├── adapters.py       # External service adapters
│   ├── factory.py        # Dependency injection factory
│   ├── messaging.py      # NATS messaging adapter
│   └── persistence.py    # Data persistence adapters
├── crossdomain/          # Anti-corruption layer
│   ├── anti_corruption.py # External service translators
│   └── adapters.py       # Cross-domain adapters
├── type_definitions/     # Type definitions and interfaces
│   ├── interfaces.py     # Port interfaces
│   ├── dto.py           # Shared DTOs
│   └── enums.py         # Shared enumerations
├── tests/               # Test suites
│   ├── unit/           # Unit tests
│   └── integration/    # Integration tests
└── k8s/                # Kubernetes deployment
    ├── templates/      # Helm templates
    └── values.yaml     # Helm values

```

### Design Patterns Used

1. **Repository Pattern**: Abstract data access behind repository interfaces
2. **Factory Pattern**: Centralized dependency injection and object creation
3. **Adapter Pattern**: Adapt external services to internal interfaces
4. **Anti-Corruption Layer**: Protect domain from external service changes
5. **Command/Query Separation**: Separate read and write operations
6. **Domain Events**: Capture significant business occurrences

## Features

### Echo Modes

- **Simple**: Returns the message as-is
- **Reverse**: Reverses the message characters
- **Uppercase**: Converts message to uppercase
- **Delayed**: Adds configurable delay before response
- **Transform**: Applies custom transformations
- **Batch**: Processes multiple messages in one request

### Service Capabilities

- RPC endpoints via NATS for echo operations
- Health monitoring with component status
- Metrics collection and reporting
- Service registration with monitor-api
- Instance tracking for load balancing visibility
- Graceful shutdown handling

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- Docker (for containerization)
- Kubernetes cluster (for deployment)
- NATS server (for messaging)
- Monitor API service (optional, for service registration)

## Installation

### Local Development Setup

#### Using uv (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd packages/aegis-sdk-examples/echo-service-ddd

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Install with development dependencies
uv pip install -e ".[dev]"

# Verify installation
aegis-validate --service-name echo-service-ddd --environment local
```

#### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

### Environment Configuration

Create a `.env` file in the project root:

```env
# Service Configuration
SERVICE_NAME=echo-service-ddd
SERVICE_PORT=8080
LOG_LEVEL=INFO

# NATS Configuration
NATS_URL=nats://localhost:4222
NATS_TOKEN=your-nats-token

# Monitor API Configuration
MONITOR_API_URL=http://localhost:8000

# Echo Service Settings
MAX_BATCH_SIZE=100
MAX_DELAY_MS=5000
METRICS_ENABLED=true
```

## Running the Service

### Local Development

```bash
# Start NATS server (using Docker)
docker run -d --name nats -p 4222:4222 nats:latest

# Run the service
uv run python main.py

# Or with custom configuration
LOG_LEVEL=DEBUG uv run python main.py
```

### Using Docker

```bash
# Build the Docker image
docker build -t echo-service-ddd .

# Run with Docker Compose (includes NATS)
docker-compose up

# Or run standalone
docker run -p 8080:8080 \
  -e NATS_URL=nats://host.docker.internal:4222 \
  echo-service-ddd
```

### Using Kubernetes

See [Deployment](#deployment) section for detailed Kubernetes instructions.

## API Documentation

### RPC Endpoints (via NATS)

#### Echo Request

**Subject**: `echo.request`

**Request Payload**:
```json
{
  "message": "Hello, World!",
  "mode": "simple",
  "priority": "normal",
  "metadata": {
    "trace_id": "abc123",
    "user_id": "user456"
  }
}
```

**Response Payload**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "original_message": "Hello, World!",
  "processed_message": "Hello, World!",
  "mode": "simple",
  "processing_time_ms": 2.5,
  "timestamp": "2024-01-01T12:00:00Z",
  "instance_id": "echo-service-abc123"
}
```

#### Batch Echo Request

**Subject**: `echo.batch`

**Request Payload**:
```json
{
  "requests": [
    {"message": "First", "mode": "simple"},
    {"message": "Second", "mode": "reverse"},
    {"message": "Third", "mode": "uppercase"}
  ]
}
```

**Response Payload**:
```json
{
  "responses": [
    {"processed_message": "First", "mode": "simple"},
    {"processed_message": "dnoceS", "mode": "reverse"},
    {"processed_message": "THIRD", "mode": "uppercase"}
  ],
  "total_processing_time_ms": 10.5,
  "batch_size": 3
}
```

### HTTP Endpoints

#### Health Check

**GET** `/health`

```json
{
  "status": "healthy",
  "service": "echo-service-ddd",
  "version": "1.0.0",
  "components": {
    "nats": "connected",
    "monitor_api": "connected"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

#### Metrics

**GET** `/metrics`

```json
{
  "requests_total": 1000,
  "requests_by_mode": {
    "simple": 400,
    "reverse": 300,
    "uppercase": 200,
    "delayed": 100
  },
  "average_processing_time_ms": 5.2,
  "errors_total": 3,
  "uptime_seconds": 3600
}
```

#### Ping

**GET** `/ping`

Returns: `pong`

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_domain.py

# Run integration tests only
uv run pytest tests/integration/

# Run with verbose output
uv run pytest -v
```

### Test Structure

- **Unit Tests**: Test individual components in isolation
  - Domain layer: Entities, value objects, domain services
  - Application layer: Use cases, handlers
  - Infrastructure layer: Adapters, factories

- **Integration Tests**: Test component interactions
  - NATS messaging integration
  - End-to-end request processing
  - Service registration flow

### Writing Tests

Tests follow TDD principles with the naming convention:
```python
def test_{functionality}_{expected_behavior}():
    # Arrange
    # Act
    # Assert
```

## Deployment

### Kubernetes with Helm

#### Quick Start

```bash
# Navigate to service directory
cd packages/aegis-sdk-examples/echo-service-ddd

# Install with default values
helm install echo-service ./k8s

# Install with custom values
helm install echo-service ./k8s -f ./k8s/values-prod.yaml

# Upgrade deployment
helm upgrade echo-service ./k8s --set image.tag=v2.0.0

# Uninstall
helm uninstall echo-service
```

#### Environment-Specific Deployments

```bash
# Development environment
helm install echo-service ./k8s \
  -f ./k8s/values-dev.yaml \
  -n development \
  --create-namespace

# Production environment
helm install echo-service ./k8s \
  -f ./k8s/values-prod.yaml \
  -n production \
  --create-namespace
```

#### Verify Deployment

```bash
# Check pod status
kubectl get pods -l app.kubernetes.io/name=echo-service-ddd

# View logs
kubectl logs -l app.kubernetes.io/name=echo-service-ddd -f

# Port forward for testing
kubectl port-forward service/echo-service-echo-service-ddd 8080:80

# Test health endpoint
curl http://localhost:8080/health
```

### Configuration Options

Key Helm values for customization:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of pod replicas | `2` |
| `image.repository` | Container image repository | `echo-service-ddd` |
| `image.tag` | Container image tag | `latest` |
| `nats.url` | NATS server URL | `nats://nats:4222` |
| `monitorApi.url` | Monitor API URL | `http://monitor-api:8000` |
| `resources.limits.memory` | Memory limit | `512Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |

## Troubleshooting

### Common Issues

#### Service Won't Start

1. **NATS Connection Failed**
   ```bash
   # Check NATS connectivity
   nc -zv localhost 4222

   # Verify NATS URL in environment
   echo $NATS_URL
   ```

2. **Port Already in Use**
   ```bash
   # Find process using port
   lsof -i :8080

   # Change port in .env
   SERVICE_PORT=8081
   ```

#### Tests Failing

1. **Import Errors**
   ```bash
   # Ensure package is installed
   uv pip install -e .

   # Check Python path
   python -c "import sys; print(sys.path)"
   ```

2. **Async Test Issues**
   ```bash
   # Install async test support
   uv pip install pytest-asyncio
   ```

#### Kubernetes Deployment Issues

1. **Pods Not Starting**
   ```bash
   # Check pod events
   kubectl describe pod <pod-name>

   # Check logs
   kubectl logs <pod-name> --previous
   ```

2. **Service Not Accessible**
   ```bash
   # Verify service endpoints
   kubectl get endpoints

   # Check service configuration
   kubectl describe service echo-service-echo-service-ddd
   ```

### Debug Mode

Enable debug logging for more information:

```bash
# Local development
LOG_LEVEL=DEBUG uv run python main.py

# Kubernetes
helm upgrade echo-service ./k8s --set logLevel=DEBUG
```

## Development Notes

### Adding New Echo Modes

1. Add mode to `EchoMode` enum in `domain/value_objects.py`
2. Implement processing logic in `domain/services.py`
3. Add tests in `tests/unit/test_domain.py`
4. Update API documentation

### Extending the Domain

Follow DDD principles when adding features:
- Keep domain logic in the domain layer
- Use value objects for concepts without identity
- Define repository interfaces in domain layer
- Implement repositories in infrastructure layer

### Code Style

The project follows:
- Python 3.13+ with type hints
- Black for formatting
- Ruff for linting
- MyPy for type checking
- Conventional Commits for git messages

## Known Issues

See [AEGIS_SDK_DEV_ISSUES.md](./AEGIS_SDK_DEV_ISSUES.md) for a comprehensive list of issues found during development with aegis-sdk-dev bootstrap tools.

Key issues:
- Bootstrap template structure needs reorganization for Helm
- Missing functional examples in generated code
- aegis-validate false positives
- No main.py entry point generated

## Contributing

When contributing to this example:
1. Follow TDD principles - write tests first
2. Maintain layer separation - no cross-layer dependencies
3. Update documentation for new features
4. Ensure all tests pass before committing
5. Use conventional commit messages

## License

This example is part of the AegisTrader project and follows the same license terms.

## Support

For issues related to:
- **This example**: Create an issue in the main repository
- **aegis-sdk-dev**: Report in the aegis-sdk-dev package issues
- **AegisSDK**: Consult the SDK documentation

## Acknowledgments

This example was created to validate and improve the aegis-sdk-dev bootstrap tools and demonstrate best practices for DDD implementation with AegisSDK.
