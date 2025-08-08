# AegisSDK Developer Tools

[![Test Coverage](https://img.shields.io/badge/coverage-43%25-yellow)](https://github.com/AegisTrader/packages/aegis-sdk-dev)
[![Unit Tests](https://img.shields.io/badge/unit%20tests-464-blue)](https://github.com/AegisTrader/packages/aegis-sdk-dev)
[![Integration Tests](https://img.shields.io/badge/integration%20tests-31-blue)](https://github.com/AegisTrader/packages/aegis-sdk-dev)
[![Architecture](https://img.shields.io/badge/architecture-hexagonal-green)](https://github.com/AegisTrader/packages/aegis-sdk-dev)
[![Type Safety](https://img.shields.io/badge/type%20safety-Pydantic%20v2-green)](https://github.com/AegisTrader/packages/aegis-sdk-dev)
[![TDD](https://img.shields.io/badge/methodology-TDD-green)](https://github.com/AegisTrader/packages/aegis-sdk-dev)

Professional developer tools and utilities for building services with AegisSDK.

## 🎯 Purpose

`aegis-sdk-dev` provides essential tools for:
- Rapid service development and prototyping
- Configuration validation and troubleshooting
- Testing utilities and fixtures
- CLI tools for common operations

## 📊 Quick Status

| Metric | Value | Status |
|--------|-------|--------|
| **Test Coverage** | 43% | 🟡 Below target (60%) |
| **Unit Tests** | 464 tests (90 passing, 17 failing) | 🟡 81% pass rate |
| **Integration Tests** | 31 tests (2 passing, 1 failing) | 🟢 67% pass rate |
| **Architecture Compliance** | ✅ Hexagonal | 🟢 Validated |
| **Type Safety** | ✅ Pydantic v2 | 🟢 Strict mode enabled |
| **TDD Practice** | ✅ Test-first | 🟢 Following Red-Green-Refactor |

## 📦 Installation

```bash
pip install aegis-sdk-dev
```

For development:
```bash
# Clone the repository
git clone https://github.com/AegisTrader/aegis-sdk-dev.git
cd packages/aegis-sdk-dev

# Install with uv (recommended)
uv sync --dev

# Or with pip
pip install -e ".[dev]"
```

## 🛠️ CLI Tools

After installation, the following CLI tools are available:

### aegis-validate

Validate and troubleshoot your service configuration:

```bash
# Basic validation
aegis-validate --service-name my-service --nats-url nats://localhost:4222

# With JSON output
aegis-validate -s my-service -n nats://localhost:4222 --json

# Auto-detect environment
aegis-validate -s my-service -e auto
```

**Features:**
- NATS connectivity testing
- Kubernetes environment detection
- Configuration recommendations
- Detailed diagnostics output

### aegis-quickstart

Interactive service creation wizard:

```bash
aegis-quickstart
```

**Features:**
- Template selection
- Configuration generation
- Project structure setup
- Dependency management

### aegis-bootstrap

Bootstrap a new service from templates:

```bash
aegis-bootstrap --template hello-world --name my-service
```

### aegis-test

Run tests with enhanced reporting:

```bash
aegis-test --coverage --watch
```

## 🐍 Python API

### Bootstrap Utilities

```python
from aegis_sdk_dev.quickstart.bootstrap import (
    create_service_context,
    BootstrapConfig,
    ServiceContext,
    cleanup_service_context
)

# Quick setup with validation
config = BootstrapConfig(
    nats_url="nats://localhost:4222",
    service_name="my-service",
    enable_watchable=True
)

# Create service context
context = await create_service_context(
    nats_url=config.nats_url,
    service_name=config.service_name
)

# Use the context
await context.message_bus.publish("test", b"Hello")

# Cleanup
await cleanup_service_context(context)
```

### Configuration Validation

```python
from aegis_sdk_dev.cli.config_validator import (
    ConfigValidator,
    ValidationResult,
    ValidationIssue
)

validator = ConfigValidator()

# Validate configuration
result = await validator.validate_configuration(
    service_name="my-service",
    nats_url="nats://localhost:4222",
    environment="auto"
)

# Check results
if result.is_valid:
    print("Configuration is valid!")
else:
    for issue in result.get_issues_by_level("ERROR"):
        print(f"Error: {issue.message}")
        print(f"Resolution: {issue.resolution}")
```

### Testing Utilities

```python
from aegis_sdk_dev.testing.environment import TestEnvironment
from aegis_sdk_dev.testing.fixtures import ServiceFixture

# Setup test environment
test_env = TestEnvironment(
    nats_url="nats://localhost:4222",
    service_name="test-service"
)

# Create fixtures
fixture = ServiceFixture(
    name="test-fixture",
    url="nats://localhost:4222"
)
```

## 🧪 Testing

### Test Coverage Status

| Component | Coverage | Status |
|-----------|----------|--------|
| **Overall** | 43% | 🟡 Needs Improvement |
| **Domain Layer** | 94% | 🟢 Excellent |
| **Application Layer** | 67% | 🟡 Good |
| **Infrastructure Layer** | 0% | 🔴 Critical Gap |
| **Ports (Interfaces)** | 100% | 🟢 Excellent |
| **CLI Tools** | 0% | 🔴 Critical Gap |

### Test Statistics

- **Total Unit Tests**: 464 test methods across 21 test files
- **Total Integration Tests**: 31 test methods across 5 test files
- **Test Execution**: ~13 seconds for unit tests
- **Lines Covered**: 538 / 1253 total lines

### Running Tests

#### Unit Tests with Coverage
```bash
# Run all unit tests with coverage report
uv run python -m pytest tests/unit/ --cov=aegis_sdk_dev --cov-report=term-missing

# Run specific test modules
uv run python -m pytest tests/unit/domain/ --cov=aegis_sdk_dev.domain
uv run python -m pytest tests/unit/application/ --cov=aegis_sdk_dev.application

# Run with minimal output
uv run python -m pytest tests/unit/ -q --tb=short
```

#### Integration Tests
```bash
# Run all integration tests (requires NATS running)
uv run python -m pytest tests/integration/ -v

# Run specific integration test
uv run python -m pytest tests/integration/test_nats_connectivity.py -v

# Run with markers
uv run python -m pytest tests/integration/ -m "not k8s" -v
```

#### Continuous Testing
```bash
# Watch mode for development
uv run python -m pytest tests/unit/ --watch

# Run tests on file changes
aegis-test --watch --coverage
```

### Coverage Goals

| Priority | Target | Current | Gap |
|----------|--------|---------|-----|
| **Phase 1** | 60% | 43% | 17% |
| **Phase 2** | 80% | - | 37% |
| **Phase 3** | 90% | - | 47% |

### Known Issues & Improvements Needed

#### Critical Gaps
1. **Infrastructure Layer** (0% coverage)
   - All adapters need unit test coverage
   - Mock external dependencies properly
   - Test error handling paths

2. **CLI Tools** (0% coverage)
   - Add unit tests for all CLI commands
   - Test argument parsing and validation
   - Mock external service calls

#### Test Failures
- **Domain Services**: 9 failures in project generation tests
  - File path assertion issues (relative vs absolute paths)
  - Missing ExecutionResult import in some tests
- **Application Layer**: 8 failures in edge case tests
  - Input validation edge cases need fixing
  - Error handling for None/invalid inputs

#### Recommended Actions
1. Fix failing tests in domain and application layers
2. Add comprehensive infrastructure adapter tests
3. Implement CLI command unit tests
4. Add integration tests for K8s environments
5. Improve test execution speed (currently timing out on full runs)

## 🏗️ Architecture

The package follows hexagonal architecture principles with strict separation of concerns:

```
aegis_sdk_dev/
├── domain/           # Business logic (94% coverage)
│   ├── models.py     # Pydantic v2 domain models
│   └── services.py   # Domain services
├── application/      # Use cases (67% coverage)
│   ├── bootstrap_service.py
│   ├── project_generator_service.py
│   ├── test_runner_service.py
│   └── validation_service.py
├── infrastructure/   # Adapters (0% coverage - needs work)
│   ├── configuration_adapter.py
│   ├── console_adapter.py
│   ├── environment_adapter.py
│   ├── file_system_adapter.py
│   ├── nats_adapter.py
│   └── process_executor_adapter.py
├── ports/           # Interfaces (100% coverage)
│   ├── configuration.py
│   ├── console.py
│   ├── environment.py
│   ├── file_system.py
│   ├── nats.py
│   └── process.py
├── cli/             # CLI interfaces (0% coverage - needs work)
│   ├── bootstrap.py
│   ├── config_validator.py
│   ├── quickstart.py
│   └── test_runner.py
├── quickstart/      # Rapid development tools
│   ├── bootstrap.py
│   └── runners.py
└── testing/         # Testing utilities
    ├── environment.py
    └── fixtures.py
```

### Architecture Validation

✅ **Hexagonal Architecture**: Proper separation between domain, application, and infrastructure layers
✅ **TDD Methodology**: Test-first development with comprehensive test suites
✅ **Pydantic v2 Type Safety**: All models use strict validation with Pydantic v2
✅ **Dependency Inversion**: Ports define contracts, adapters implement them
✅ **Clean Code**: Following SOLID principles and clean code practices

## 🔧 Features

### Type Safety with Pydantic v2

All configurations use Pydantic models with strict validation:

```python
from pydantic import BaseModel, Field

class BootstrapConfig(BaseModel):
    nats_url: str = Field(..., description="NATS connection URL")
    service_name: str = Field(..., min_length=1)
    kv_bucket: str = Field(default="service_registry")
    enable_watchable: bool = Field(default=True)

    model_config = {"strict": True, "frozen": True}
```

### Rich Console Output

Beautiful, informative output using Rich:

```python
from rich.console import Console
from rich.table import Table

console = Console()
table = Table(title="Validation Results")
table.add_column("Check", style="cyan")
table.add_column("Status", style="green")
table.add_row("NATS Connection", "✓ Connected")
table.add_row("K8s Environment", "✓ Detected")
console.print(table)
```

### Async-First Design

All tools are built with async/await:

```python
async def validate_nats_connection(url: str) -> bool:
    async with NATSClient() as client:
        return await client.connect(url)
```

## 📊 Configuration Validation

The validation system checks:

- **NATS Connectivity**: Connection testing with timeout
- **Environment Detection**: Kubernetes, Docker, local
- **Service Configuration**: Name validation, port checks
- **Network Access**: Port forwarding requirements
- **Dependencies**: Required services availability

Example validation output:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Validation Summary     ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ✓ VALID                │
│ Environment: kubernetes│
└────────────────────────┘

Validation Issues
┌───────┬──────────┬──────────────────────┬─────────────────────┐
│ Level │ Category │ Message              │ Resolution          │
├───────┼──────────┼──────────────────────┼─────────────────────┤
│ INFO  │ K8S      │ Running in K8s       │ Configuration OK    │
└───────┴──────────┴──────────────────────┴─────────────────────┘

Diagnostics:
  • nats_connection: OK
  • k8s_environment: True

Recommendations:
  → Consider using service mesh for inter-service communication
```

## 🧪 Testing Support

Enhanced testing capabilities:

```python
import pytest
from aegis_sdk_dev.testing import TestEnvironment

@pytest.fixture
async def test_env():
    env = TestEnvironment()
    await env.setup()
    yield env
    await env.teardown()

async def test_service_communication(test_env):
    # Test with proper isolation
    service = await test_env.create_service("test-service")
    response = await service.call("echo", "Hello")
    assert response == "Hello"
```

## 🚀 Quick Start Templates

Bootstrap new services quickly:

```bash
# List available templates
aegis-quickstart --list-templates

# Create from template
aegis-quickstart --template trading-service --name my-trading-service
```

Available templates:
- `hello-world` - Minimal service with hexagonal architecture
- `echo-service` - Bidirectional communication example
- `trading-service` - Domain-driven trading service
- `event-driven` - Event sourcing pattern
- `single-active` - Leader election pattern

## 🔍 Troubleshooting

Common issues and solutions:

### NATS Connection Failed

```bash
aegis-validate -s test -n nats://localhost:4222
```

**Resolution:**
1. Check NATS is running: `docker ps | grep nats`
2. For K8s: `kubectl port-forward -n aegis svc/nats 4222:4222`
3. Verify firewall rules

### Configuration Invalid

```bash
aegis-validate --json | jq '.issues'
```

**Resolution:**
1. Review validation output
2. Check environment variables
3. Verify service names match

## 📝 Best Practices

1. **Always validate configuration** before deployment
2. **Use type-safe configurations** with Pydantic models
3. **Bootstrap services** using provided utilities
4. **Test with proper isolation** using test environments
5. **Monitor validation results** in CI/CD pipelines

## 🚀 CI/CD Integration

### GitHub Actions Workflow

```yaml
name: aegis-sdk-dev CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: |
          cd packages/aegis-sdk-dev
          uv sync --dev

      - name: Run unit tests with coverage
        run: |
          cd packages/aegis-sdk-dev
          uv run python -m pytest tests/unit/ \
            --cov=aegis_sdk_dev \
            --cov-report=xml \
            --cov-report=term

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./packages/aegis-sdk-dev/coverage.xml
          fail_ci_if_error: true
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: aegis-sdk-dev-tests
        name: AegisSDK Dev Tests
        entry: bash -c 'cd packages/aegis-sdk-dev && uv run python -m pytest tests/unit/ -q'
        language: system
        pass_filenames: false
        files: ^packages/aegis-sdk-dev/
```

### Development Workflow

1. **Before Committing**:
   ```bash
   # Run unit tests
   uv run python -m pytest tests/unit/ --cov=aegis_sdk_dev

   # Run type checking
   uv run mypy aegis_sdk_dev

   # Run linting
   uv run ruff check aegis_sdk_dev
   ```

2. **Before PR**:
   ```bash
   # Full test suite
   uv run python -m pytest tests/ --cov=aegis_sdk_dev --cov-report=html

   # Check coverage report
   open htmlcov/index.html
   ```

3. **Integration Testing** (requires NATS):
   ```bash
   # Start NATS locally
   docker run -d -p 4222:4222 nats:latest

   # Run integration tests
   uv run python -m pytest tests/integration/ -v
   ```

## 🤝 Contributing

We welcome contributions! Priority areas for improvement:

### High Priority
1. **Infrastructure Layer Testing** (0% → 80% coverage)
   - Mock adapters for all external dependencies
   - Test error handling and edge cases
   - Add integration tests for NATS adapter

2. **CLI Tools Testing** (0% → 70% coverage)
   - Unit tests for all CLI commands
   - Test argument parsing and validation
   - Mock service interactions

3. **Fix Failing Tests** (17 failures)
   - Domain service test path issues
   - Application layer edge case handling
   - Missing imports and type definitions

### Medium Priority
- Additional CLI tools for development workflow
- More project templates (gRPC, GraphQL, WebSocket)
- Performance testing utilities
- Documentation generation tools

### How to Contribute
1. Check existing issues or create a new one
2. Fork the repository
3. Create a feature branch
4. Write tests first (TDD approach)
5. Implement your changes
6. Ensure all tests pass with good coverage
7. Submit a pull request

## 📄 License

Same license as AegisSDK core.

## 🆘 Support

- GitHub Issues: Tag with `dev-tools`
- Documentation: See examples package
- Community: Join our Discord

---

**Note**: This package is for development only. Do not include it in production dependencies.
