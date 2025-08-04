# AegisSDK Test-Driven Development Strategy

## Overview

This document outlines the TDD strategy for AegisSDK following the Red-Green-Refactor cycle and hexagonal architecture principles.

## TDD Workflow

### 1. RED Phase - Write Failing Tests First

Before implementing any feature:

```python
# Example: Test for new service registration feature
@pytest.mark.asyncio
async def test_service_registers_on_start():
    """Test that service automatically registers when started."""
    # Arrange
    mock_registry = Mock(spec=ServiceRegistryPort)
    mock_bus = Mock(spec=MessageBusPort)

    service = Service(
        service_name="test-service",
        message_bus=mock_bus,
        service_registry=mock_registry,
    )

    # Act
    await service.start()

    # Assert
    mock_registry.register.assert_called_once()
    instance = mock_registry.register.call_args[0][0]
    assert instance.service_name == "test-service"
    assert instance.status == "ACTIVE"
```

### 2. GREEN Phase - Minimal Implementation

Implement just enough code to make the test pass:

```python
class Service:
    async def start(self) -> None:
        """Start the service with minimal implementation."""
        if self._registry:
            instance = ServiceInstance(
                service_name=self.service_name,
                instance_id=self.instance_id,
                version=self.version,
                status="ACTIVE",
            )
            await self._registry.register(instance, ttl_seconds=self._registry_ttl)
```

### 3. REFACTOR Phase - Improve Design

After tests pass, refactor for better design:

```python
class Service:
    async def start(self) -> None:
        """Start the service with improved design."""
        await self._initialize_components()
        await self._register_service()
        await self._start_background_tasks()
        await self.on_start()  # Hook for subclasses

    async def _register_service(self) -> None:
        """Register service with proper error handling."""
        if not self._should_register():
            return

        try:
            self._service_instance = self._create_service_instance()
            await self._registry.register(
                self._service_instance,
                ttl_seconds=self._registry_ttl
            )
            self._logger.info(f"Service {self.service_name} registered")
        except Exception as e:
            self._logger.error(f"Failed to register service: {e}")
            raise ServiceRegistrationError(f"Registration failed: {e}")
```

## Test Categories by Architecture Layer

### 1. Domain Layer Tests

**Focus**: Pure business logic, no infrastructure

```python
class TestServiceInstance:
    """Test domain model with Pydantic v2 validation."""

    def test_service_instance_validation(self):
        """Test that service instance validates required fields."""
        # Valid instance
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-001",
            version="1.0.0",
        )
        assert instance.status == "ACTIVE"  # Default value

        # Invalid service name
        with pytest.raises(ValidationError) as exc_info:
            ServiceInstance(
                service_name="Test-Service",  # Capital letters not allowed
                instance_id="test-001",
                version="1.0.0",
            )
        assert "service_name" in str(exc_info.value)

    def test_service_instance_immutability(self):
        """Test that Pydantic models are immutable."""
        instance = ServiceInstance(
            service_name="test-service",
            instance_id="test-001",
            version="1.0.0",
        )

        with pytest.raises(ValidationError):
            instance.service_name = "changed-name"  # Should fail
```

### 2. Port Tests (Contract Tests)

**Focus**: Verify port interfaces are properly defined

```python
class TestServiceRegistryPort:
    """Test port contract compliance."""

    @pytest.mark.parametrize("implementation", [
        KVServiceRegistry,
        InMemoryServiceRegistry,
    ])
    def test_port_contract(self, implementation):
        """Test that implementations satisfy port contract."""
        assert hasattr(implementation, 'register')
        assert hasattr(implementation, 'deregister')
        assert hasattr(implementation, 'list_instances')

        # Verify method signatures
        register_sig = inspect.signature(implementation.register)
        assert 'instance' in register_sig.parameters
        assert 'ttl_seconds' in register_sig.parameters
```

### 3. Adapter Tests (Integration Tests)

**Focus**: Test infrastructure implementations

```python
@pytest.mark.integration
class TestNATSAdapter:
    """Test NATS adapter implementation."""

    @pytest.fixture
    async def nats_adapter(self):
        """Create NATS adapter with test configuration."""
        adapter = NATSAdapter()
        await adapter.connect(["nats://localhost:4222"])
        yield adapter
        await adapter.close()

    async def test_implements_message_bus_port(self, nats_adapter):
        """Test that NATS adapter implements MessageBusPort."""
        # Verify all required methods exist
        assert isinstance(nats_adapter, MessageBusPort)

        # Test publish
        await nats_adapter.publish("test.subject", b"test-data")

        # Test subscribe
        received = []
        async def handler(msg):
            received.append(msg)

        sub = await nats_adapter.subscribe("test.subject", handler)
        await nats_adapter.publish("test.subject", b"test-data")
        await asyncio.sleep(0.1)

        assert len(received) == 1
        await sub.unsubscribe()
```

### 4. Application Layer Tests

**Focus**: Test orchestration and use cases

```python
class TestServiceOrchestration:
    """Test service orchestration logic."""

    async def test_service_lifecycle(self):
        """Test complete service lifecycle."""
        # Arrange - Use test doubles for all ports
        mock_bus = AsyncMock(spec=MessageBusPort)
        mock_registry = AsyncMock(spec=ServiceRegistryPort)
        mock_discovery = AsyncMock(spec=ServiceDiscoveryPort)

        service = Service(
            service_name="test-service",
            message_bus=mock_bus,
            service_registry=mock_registry,
            service_discovery=mock_discovery,
        )

        # Act - Start service
        await service.start()

        # Assert - Verify orchestration
        mock_registry.register.assert_called_once()
        assert service.is_running

        # Act - Stop service
        await service.stop()

        # Assert - Verify cleanup
        mock_registry.deregister.assert_called_once()
        assert not service.is_running
```

## Test Double Strategy

### 1. Mocks for Ports
Use mocks for port interfaces in unit tests:

```python
mock_registry = Mock(spec=ServiceRegistryPort)
```

### 2. Fakes for Complex Behavior
Create fake implementations for complex scenarios:

```python
class FakeServiceRegistry(ServiceRegistryPort):
    """Fake implementation for testing."""

    def __init__(self):
        self._instances = {}

    async def register(self, instance: ServiceInstance, ttl_seconds: int = 30):
        self._instances[instance.instance_id] = instance

    async def list_instances(self, service_name: str) -> list[ServiceInstance]:
        return [i for i in self._instances.values() if i.service_name == service_name]
```

### 3. Stubs for External Services
Use stubs for external dependencies:

```python
class StubNATSConnection:
    """Stub NATS connection for testing."""

    async def publish(self, subject: str, data: bytes):
        # Minimal implementation
        pass
```

## Test Data Builders

### Using Pydantic Models as Builders

```python
class ServiceInstanceBuilder:
    """Builder for test service instances."""

    @staticmethod
    def build(**kwargs) -> ServiceInstance:
        """Build service instance with defaults."""
        defaults = {
            "service_name": "test-service",
            "instance_id": f"test-{uuid.uuid4().hex[:8]}",
            "version": "1.0.0",
            "status": "ACTIVE",
            "metadata": {},
        }
        defaults.update(kwargs)
        return ServiceInstance(**defaults)

# Usage in tests
instance = ServiceInstanceBuilder.build(service_name="custom-service")
```

## Property-Based Testing with Hypothesis

```python
from hypothesis import given, strategies as st
from hypothesis_pydantic import from_model

class TestServiceInstanceProperties:
    """Property-based tests for domain models."""

    @given(from_model(ServiceInstance))
    def test_service_instance_serialization(self, instance: ServiceInstance):
        """Test that all valid instances can be serialized/deserialized."""
        # Serialize
        json_data = instance.model_dump_json()

        # Deserialize
        restored = ServiceInstance.model_validate_json(json_data)

        # Assert equality
        assert restored == instance

    @given(
        service_name=st.from_regex(r'^[a-z][a-z0-9-]*$'),
        version=st.from_regex(r'^\d+\.\d+\.\d+$'),
    )
    def test_service_name_validation(self, service_name: str, version: str):
        """Test that valid service names are accepted."""
        instance = ServiceInstance(
            service_name=service_name,
            instance_id="test-001",
            version=version,
        )
        assert instance.service_name == service_name
```

## Continuous Testing Strategy

### 1. Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: test-changed
        name: Run tests for changed files
        entry: pytest
        language: system
        files: \.py$
        pass_filenames: false
        args: [--testmon, --testmon-nocollect]
```

### 2. Test Coverage Requirements

```ini
# pytest.ini
[tool:pytest]
minversion = 6.0
testpaths = tests
addopts =
    --cov=aegis_sdk
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=90
    --strict-markers
    -vv

markers =
    unit: Unit tests (no external dependencies)
    integration: Integration tests (require infrastructure)
    e2e: End-to-end tests (full stack)
```

### 3. Mutation Testing

```python
# Run mutation testing to verify test quality
# pip install mutmut
# mutmut run --paths-to-mutate=aegis_sdk/domain
```

## Test Maintenance Guidelines

### 1. Test Naming Convention
```python
def test_<unit>_<scenario>_<expected_result>():
    """Test description following Given-When-Then."""
    pass

# Example:
def test_service_registry_register_with_ttl_expires_after_timeout():
    """Given a service instance with TTL, when registered, then expires after timeout."""
    pass
```

### 2. Test Organization
```
tests/
├── unit/
│   ├── domain/          # Pure domain logic
│   ├── application/     # Application services
│   └── ports/          # Port contracts
├── integration/
│   ├── adapters/       # Infrastructure adapters
│   └── e2e/           # End-to-end scenarios
└── fixtures/          # Shared test fixtures
```

### 3. Test Documentation
Each test should include:
- Clear description of what is being tested
- Explanation of the business rule being verified
- Links to relevant requirements or issues

## Conclusion

This TDD strategy ensures:
1. **Test-First Development**: All features start with failing tests
2. **Architecture Integrity**: Tests enforce hexagonal boundaries
3. **Type Safety**: Pydantic v2 validation throughout
4. **Maintainability**: Clear test organization and documentation
5. **Continuous Quality**: Automated testing at all levels

Follow this strategy to maintain high code quality and architectural integrity in AegisSDK.
