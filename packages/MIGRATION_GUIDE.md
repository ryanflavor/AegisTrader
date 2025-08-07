# AegisSDK Package Refactoring Migration Guide

## Overview

AegisSDK has been refactored into three separate packages to provide better separation of concerns and a world-class developer experience:

1. **aegis-sdk** - Core SDK for production use
2. **aegis-sdk-dev** - Developer tools and utilities
3. **aegis-sdk-examples** - Comprehensive example applications

## Migration Steps

### 1. Update Dependencies

**Before (single package):**
```toml
[dependencies]
aegis-sdk = "1.0.1"
```

**After (modular packages):**
```toml
[dependencies]
aegis-sdk = "1.0.1"  # Core SDK only

[dev-dependencies]
aegis-sdk-dev = "1.0.0"  # Developer tools
```

For learning and examples:
```bash
pip install aegis-sdk-examples
```

### 2. Update Imports

#### Developer Tools

**Before:**
```python
from aegis_sdk.developer.bootstrap import bootstrap_sdk
from aegis_sdk.developer.config_helper import SDKConfig
from aegis_sdk.developer.environment import Environment
```

**After:**
```python
from aegis_sdk_dev.quickstart.bootstrap import bootstrap_sdk
from aegis_sdk_dev.cli.config_validator import ConfigValidator
from aegis_sdk_dev.testing.environment import TestEnvironment
```

#### Examples

**Before:**
```python
# Examples were in aegis_sdk/examples/
from aegis_sdk.examples.quickstart.echo_service import ...
```

**After:**
```python
# Examples are now standalone with proper structure
# See aegis-sdk-examples/basic/hello-world/
# Each example is a complete application with hexagonal architecture
```

### 3. CLI Tools

New CLI tools are available after installing `aegis-sdk-dev`:

```bash
# Configuration validation
aegis-validate --service-name my-service --nats-url nats://localhost:4222

# Quickstart wizard
aegis-quickstart

# Bootstrap new service
aegis-bootstrap

# Run tests
aegis-test
```

### 4. Example Structure

Examples now follow a consistent, educational structure:

```
aegis-sdk-examples/
├── basic/
│   ├── hello-world/      # Minimal service with hexagonal architecture
│   ├── echo-service/      # Bidirectional communication
│   └── simple-rpc/        # Request-response patterns
├── intermediate/
│   ├── trading-service/   # Domain-driven trading example
│   ├── event-driven/      # Event sourcing patterns
│   └── single-active/     # Leader election patterns
├── advanced/
│   ├── saga-pattern/      # Distributed transactions
│   ├── cqrs-example/      # Command Query Responsibility Segregation
│   └── full-trading-system/ # Complete production-ready system
└── tutorials/
    ├── 01-getting-started/
    ├── 02-ddd-patterns/
    └── 03-production-deployment/
```

Each example includes:
- Full hexagonal architecture implementation
- Comprehensive tests (unit, integration)
- Pydantic v2 models with strict validation
- Docker and Kubernetes deployment files
- Detailed README with learning objectives

### 5. Testing Utilities

**Before:**
```python
# Limited testing utilities
from aegis_sdk.developer.test_runner import run_tests
```

**After:**
```python
from aegis_sdk_dev.testing.environment import TestEnvironment
from aegis_sdk_dev.testing.fixtures import ServiceFixture

# Better test isolation and setup
test_env = TestEnvironment(
    nats_url="nats://localhost:4222",
    service_name="test-service"
)
```

## Benefits of the New Structure

1. **Cleaner Production Dependencies**: The core SDK only includes what's needed for production
2. **Better Developer Experience**: Dedicated tools package with CLI utilities
3. **Educational Examples**: World-class examples demonstrating best practices
4. **Type Safety**: All packages use Pydantic v2 with strict validation
5. **Hexagonal Architecture**: Clear separation of concerns in all examples
6. **TDD Approach**: Examples include comprehensive test suites

## Backward Compatibility

- Deprecation warnings have been added to old import paths
- The old structure will continue to work temporarily
- Plan to migrate within the next major version release

## Getting Help

- Check the examples in `aegis-sdk-examples` for patterns and best practices
- Use `aegis-validate` to troubleshoot configuration issues
- Refer to individual package READMEs for detailed documentation

## Example: Migrating a Service

Here's a complete migration example:

**Before:**
```python
from aegis_sdk.developer.bootstrap import bootstrap_sdk
from aegis_sdk.examples.quickstart.echo_service import EchoService

async def main():
    components = await bootstrap_sdk("nats://localhost:4222", "my-service")
    service = EchoService(components)
    await service.run()
```

**After:**
```python
from aegis_sdk_dev.quickstart.bootstrap import create_service_context
from aegis_sdk.application.service import Service
from aegis_sdk.domain.models import ServiceInfo
from pydantic import BaseModel

class ServiceConfig(BaseModel):
    """Service configuration with validation."""
    nats_url: str
    service_name: str
    
    model_config = {"strict": True}

async def main():
    config = ServiceConfig(
        nats_url="nats://localhost:4222",
        service_name="my-service"
    )
    
    # Create context with proper dependency injection
    context = await create_service_context(
        nats_url=config.nats_url,
        service_name=config.service_name
    )
    
    # Use the service with hexagonal architecture
    service = Service(
        message_bus=context.message_bus,
        service_registry=context.service_registry,
        logger=context.logger
    )
    
    await service.run()
```

## Timeline

- **Current**: Both old and new structures work with deprecation warnings
- **Next Minor Release**: Documentation will only reference new structure
- **Next Major Release**: Old structure will be removed

## Questions?

For questions or issues with migration, please:
1. Check the example applications in `aegis-sdk-examples`
2. Use the validation tool: `aegis-validate`
3. Open an issue on GitHub with the migration tag