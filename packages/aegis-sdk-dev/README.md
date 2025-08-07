# AegisSDK Developer Tools

Professional developer tools and utilities for building services with AegisSDK.

## 🎯 Purpose

`aegis-sdk-dev` provides essential tools for:
- Rapid service development and prototyping
- Configuration validation and troubleshooting
- Testing utilities and fixtures
- CLI tools for common operations

## 📦 Installation

```bash
pip install aegis-sdk-dev
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

## 🏗️ Architecture

The package follows hexagonal architecture principles:

```
aegis_sdk_dev/
├── cli/              # Command-line interfaces
│   ├── bootstrap.py
│   ├── config_validator.py
│   ├── quickstart.py
│   └── test_runner.py
├── quickstart/       # Rapid development tools
│   ├── bootstrap.py  # Service bootstrapping
│   └── runners.py    # Quickstart runners
└── testing/          # Testing utilities
    ├── environment.py # Test environment setup
    └── fixtures.py    # Test fixtures
```

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

## 🤝 Contributing

We welcome contributions! Areas of interest:
- Additional CLI tools
- More testing utilities
- Template improvements
- Documentation enhancements

## 📄 License

Same license as AegisSDK core.

## 🆘 Support

- GitHub Issues: Tag with `dev-tools`
- Documentation: See examples package
- Community: Join our Discord

---

**Note**: This package is for development only. Do not include it in production dependencies.