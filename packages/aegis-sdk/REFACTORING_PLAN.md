# AegisSDK Refactoring Plan - TDD & Hexagonal Architecture

## Immediate Refactoring Tasks

### Phase 1: Fix Failing Integration Tests (Red → Green)

#### 1.1 Update Service Discovery Integration Tests

**File**: `tests/integration/test_service_discovery_k8s_integration.py`

**Current Issue**: Tests use old Service API with direct infrastructure dependencies

**Refactoring Steps**:
```python
# BEFORE (Infrastructure coupling):
service = Service(
    name="test-service",
    adapter=nats_adapter,      # ❌ Infrastructure dependency
    kv_store=kv_store,         # ❌ Infrastructure dependency
    logger=logger,
    metrics=metrics,
)

# AFTER (Port abstraction):
# Step 1: Create port implementations
message_bus = nats_adapter  # NATSAdapter implements MessageBusPort
service_registry = KVServiceRegistry(kv_store)
service_discovery = BasicServiceDiscovery(service_registry)

# Step 2: Create service with ports
service = Service(
    service_name="test-service",
    message_bus=message_bus,        # ✅ Port abstraction
    service_registry=service_registry,    # ✅ Port abstraction
    service_discovery=service_discovery,  # ✅ Port abstraction
    logger=logger,
)
```

#### 1.2 Create Test Fixtures Following Hexagonal Pattern

**New File**: `tests/fixtures/hexagonal_fixtures.py`

```python
import pytest
from unittest.mock import AsyncMock, Mock
from aegis_sdk.ports import (
    MessageBusPort,
    ServiceRegistryPort,
    ServiceDiscoveryPort,
    LoggerPort,
)

@pytest.fixture
def mock_message_bus():
    """Create mock message bus for unit tests."""
    return AsyncMock(spec=MessageBusPort)

@pytest.fixture
def mock_service_registry():
    """Create mock service registry for unit tests."""
    return AsyncMock(spec=ServiceRegistryPort)

@pytest.fixture
def mock_service_discovery():
    """Create mock service discovery for unit tests."""
    return AsyncMock(spec=ServiceDiscoveryPort)

@pytest.fixture
async def real_message_bus(nats_adapter):
    """Create real message bus for integration tests."""
    return nats_adapter  # NATSAdapter implements MessageBusPort

@pytest.fixture
async def real_service_registry(kv_store):
    """Create real service registry for integration tests."""
    return KVServiceRegistry(kv_store)
```

### Phase 2: Improve Type Safety with Pydantic v2

#### 2.1 Create Configuration Models

**New File**: `aegis_sdk/domain/config.py`

```python
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional

class ServiceConfig(BaseModel):
    """Service configuration with strict validation."""

    model_config = ConfigDict(
        strict=True,
        validate_assignment=True,
        extra="forbid",
    )

    service_name: str = Field(
        ...,
        pattern=r'^[a-z][a-z0-9-]*$',
        min_length=1,
        max_length=63,
        description="Service name following k8s naming convention"
    )

    version: str = Field(
        ...,
        pattern=r'^\d+\.\d+\.\d+$',
        description="Semantic version (e.g., 1.0.0)"
    )

    instance_id: Optional[str] = Field(
        default=None,
        pattern=r'^[a-zA-Z0-9-]+$',
        description="Unique instance identifier"
    )

    registry_ttl: int = Field(
        default=30,
        gt=0,
        le=3600,
        description="Registry TTL in seconds"
    )

    heartbeat_interval: int = Field(
        default=10,
        gt=0,
        le=300,
        description="Heartbeat interval in seconds"
    )

    enable_registration: bool = Field(
        default=True,
        description="Enable automatic service registration"
    )

    @field_validator("heartbeat_interval")
    @classmethod
    def validate_heartbeat_interval(cls, v: int, info) -> int:
        """Ensure heartbeat interval is less than TTL."""
        if "registry_ttl" in info.data:
            ttl = info.data["registry_ttl"]
            if v >= ttl:
                raise ValueError(
                    f"Heartbeat interval ({v}s) must be less than TTL ({ttl}s)"
                )
        return v
```

#### 2.2 Refactor Service Class to Use Config

```python
class Service:
    """Service with configuration-driven initialization."""

    def __init__(
        self,
        config: ServiceConfig,
        message_bus: MessageBusPort,
        service_registry: Optional[ServiceRegistryPort] = None,
        service_discovery: Optional[ServiceDiscoveryPort] = None,
        logger: Optional[LoggerPort] = None,
    ):
        """Initialize service with validated configuration."""
        self._config = config
        self._bus = message_bus
        self._registry = service_registry
        self._discovery = service_discovery
        self._logger = logger or NullLogger()

        # Derive instance ID if not provided
        if not self._config.instance_id:
            self._config.instance_id = f"{config.service_name}-{uuid.uuid4().hex[:8]}"
```

### Phase 3: Implement Missing Port Tests

#### 3.1 Port Contract Tests

**New File**: `tests/unit/ports/test_port_contracts.py`

```python
import pytest
from abc import ABC, abstractmethod
import inspect
from typing import Protocol

from aegis_sdk.ports import (
    MessageBusPort,
    ServiceRegistryPort,
    ServiceDiscoveryPort,
)

class PortContractTest(ABC):
    """Base class for port contract tests."""

    @abstractmethod
    def get_port_interface(self) -> type[Protocol]:
        """Return the port interface to test."""
        pass

    @abstractmethod
    def get_implementations(self) -> list[type]:
        """Return list of implementations to test."""
        pass

    def test_implementations_satisfy_contract(self):
        """Test that all implementations satisfy the port contract."""
        port = self.get_port_interface()
        required_methods = self._get_required_methods(port)

        for impl in self.get_implementations():
            for method_name, method_sig in required_methods.items():
                assert hasattr(impl, method_name), \
                    f"{impl.__name__} missing required method: {method_name}"

                impl_method = getattr(impl, method_name)
                impl_sig = inspect.signature(impl_method)

                # Verify signatures match (excluding self)
                self._assert_signatures_compatible(
                    method_name, method_sig, impl_sig, impl.__name__
                )

class TestMessageBusPort(PortContractTest):
    """Test MessageBusPort contract compliance."""

    def get_port_interface(self):
        return MessageBusPort

    def get_implementations(self):
        from aegis_sdk.infrastructure import NATSAdapter
        return [NATSAdapter]
```

### Phase 4: Refactor Tests Following TDD

#### 4.1 Create TDD Test Template

**New File**: `tests/templates/tdd_template.py`

```python
"""
TDD Test Template for AegisSDK

Follow the Red-Green-Refactor cycle:
1. RED: Write failing test first
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve design while keeping tests green
"""

import pytest
from unittest.mock import Mock, AsyncMock

class TestFeatureName:
    """Test [Feature] following TDD principles."""

    # RED Phase - Write failing tests first

    @pytest.mark.asyncio
    async def test_feature_behavior_given_scenario(self):
        """
        Given: [Initial context]
        When: [Action is performed]
        Then: [Expected outcome]
        """
        # Arrange
        # Set up test data and mocks

        # Act
        # Perform the action being tested

        # Assert
        # Verify expected behavior
        raise NotImplementedError("Write test first!")

    # GREEN Phase - Minimal implementation
    # (Implementation goes in source code, not test file)

    # REFACTOR Phase - Additional tests for edge cases

    @pytest.mark.asyncio
    async def test_feature_handles_error_condition(self):
        """Test error handling for [specific condition]."""
        pass

    @pytest.mark.asyncio
    async def test_feature_validates_input(self):
        """Test input validation with Pydantic models."""
        pass
```

### Phase 5: Architecture Improvements

#### 5.1 Introduce Factory Pattern for Service Creation

**New File**: `aegis_sdk/application/factories.py`

```python
from typing import Optional
from ..domain.config import ServiceConfig
from ..ports import MessageBusPort, ServiceRegistryPort, ServiceDiscoveryPort, LoggerPort
from .service import Service

class ServiceFactory:
    """Factory for creating services with proper dependencies."""

    @staticmethod
    def create_service(
        config: ServiceConfig,
        infrastructure_config: dict[str, str],
    ) -> Service:
        """Create service with all dependencies."""
        # Create infrastructure adapters
        nats_adapter = NATSAdapter()
        kv_store = NATSKVStore(nats_adapter)

        # Create port implementations
        message_bus = nats_adapter
        service_registry = KVServiceRegistry(kv_store)
        service_discovery = BasicServiceDiscovery(service_registry)
        logger = SimpleLogger(config.service_name)

        # Create service
        return Service(
            config=config,
            message_bus=message_bus,
            service_registry=service_registry,
            service_discovery=service_discovery,
            logger=logger,
        )

    @staticmethod
    def create_test_service(
        config: Optional[ServiceConfig] = None,
        **mock_overrides,
    ) -> Service:
        """Create service with mocked dependencies for testing."""
        if not config:
            config = ServiceConfig(
                service_name="test-service",
                version="1.0.0",
            )

        # Default mocks
        mocks = {
            "message_bus": AsyncMock(spec=MessageBusPort),
            "service_registry": AsyncMock(spec=ServiceRegistryPort),
            "service_discovery": AsyncMock(spec=ServiceDiscoveryPort),
            "logger": Mock(spec=LoggerPort),
        }

        # Apply overrides
        mocks.update(mock_overrides)

        return Service(config=config, **mocks)
```

## Implementation Timeline

### Week 1: Fix Critical Issues
- [ ] Update failing integration tests (Day 1-2)
- [ ] Create hexagonal test fixtures (Day 2-3)
- [ ] Implement port contract tests (Day 3-4)
- [ ] Add configuration models (Day 4-5)

### Week 2: Improve Architecture
- [ ] Refactor Service class with config (Day 1-2)
- [ ] Implement service factory (Day 2-3)
- [ ] Create TDD test templates (Day 3-4)
- [ ] Update documentation (Day 4-5)

### Week 3: Enhance Testing
- [ ] Add property-based tests (Day 1-2)
- [ ] Implement test builders (Day 2-3)
- [ ] Set up mutation testing (Day 3-4)
- [ ] Create CI/CD pipeline updates (Day 4-5)

## Success Metrics

1. **Test Coverage**: Maintain >90% coverage
2. **Test Execution Time**: All unit tests < 1 second
3. **Architecture Compliance**: Zero violations of hexagonal boundaries
4. **Type Safety**: 100% Pydantic validation on domain models
5. **TDD Adoption**: All new features start with failing tests

## Risk Mitigation

1. **Backward Compatibility**:
   - Keep old constructors with deprecation warnings
   - Provide migration guide for existing code

2. **Test Flakiness**:
   - Use proper async test fixtures
   - Implement retry logic for integration tests
   - Use test containers for infrastructure

3. **Performance Impact**:
   - Profile Pydantic validation overhead
   - Use lazy initialization where appropriate
   - Cache validated configurations

## Conclusion

This refactoring plan ensures:
- Adherence to TDD principles
- Proper hexagonal architecture
- Type safety with Pydantic v2
- Maintainable and testable code
- Clear separation of concerns

Follow this plan incrementally to transform the codebase while maintaining stability.
