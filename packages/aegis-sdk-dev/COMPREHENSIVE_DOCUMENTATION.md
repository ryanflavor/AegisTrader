# AegisSDK Development Tools (aegis-sdk-dev) - Comprehensive Documentation

## Overview

**AegisSDK Development Tools** (`aegis-sdk-dev`) is a comprehensive development toolkit designed for rapid microservice creation and deployment using the AegisSDK framework. It provides CLI tools, project scaffolding, code generation, and validation utilities that enable developers to go from concept to production-ready Kubernetes deployment in minutes.

### Key Value Proposition

- **5-second project creation** with enterprise-grade DDD architecture
- **3-minute Kubernetes deployment** with built-in DevOps automation
- **96% code reduction** by leveraging AegisSDK infrastructure components
- **Production-ready** services with monitoring, health checks, and cloud-native patterns

## Architecture and Components

### Core Architecture

The `aegis-sdk-dev` follows a clean hexagonal architecture with these main layers:

```
aegis-sdk-dev/
├── cli/                    # Command-line interfaces
│   ├── quickstart.py      # Interactive project wizard
│   ├── bootstrap.py       # Simple project creation
│   ├── config_validator.py # Configuration validation
│   └── test_runner.py     # Test execution
├── domain/                # Business logic and models
│   ├── models.py          # Domain entities and value objects
│   ├── services.py        # Domain services
│   ├── simple_project_generator.py # Core project generation
│   └── quickstart_generator.py # Quickstart-specific generator
├── application/           # Use cases and coordination
│   ├── project_generator_service.py
│   ├── validation_service.py
│   ├── test_runner_service.py
│   └── bootstrap_service.py
├── infrastructure/        # Technical implementations
│   ├── template_generators.py # DDD template generation
│   ├── file_system_adapter.py # File operations
│   ├── console_adapter.py # Rich console output
│   └── factory.py         # Dependency injection
└── ports/                 # Interface definitions
    ├── file_system.py
    ├── console.py
    └── template_generator.py
```

### Key Components

#### 1. **Project Templates**

Currently supports one primary template:

- **`enterprise_ddd`**: Full Domain-Driven Design with hexagonal architecture
  - Domain layer (entities, value objects, services, events)
  - Application layer (use cases, commands, queries, handlers)
  - Infrastructure layer (adapters, persistence, messaging)
  - Cross-domain layer (anti-corruption, translators)
  - Complete DevOps setup (Docker, Kubernetes, Helm)

#### 2. **Code Generation Engine**

The `SimpleProjectGenerator` creates complete project structures with:

- **Smart file content generation** based on file type and DDD patterns
- **Template-driven approach** with customizable components
- **Context-aware content** that includes proper imports and SDK usage
- **Production-ready configurations** for all environments

#### 3. **CLI Tools Integration**

Four main CLI commands available as system executables:

```bash
aegis-bootstrap    # Direct project creation
aegis-quickstart   # Interactive wizard
aegis-validate     # Configuration validation
aegis-test         # Test runner
```

## CLI Tools and Commands

### 1. `aegis-quickstart` - Interactive Wizard

**Purpose**: Full-featured interactive wizard for new developers

**Features**:
- Step-by-step project configuration
- Feature selection (Docker, Kubernetes, examples)
- Environment setup automation
- Git repository initialization
- Dependency installation with `uv`

**Usage**:
```bash
# Interactive mode (recommended for new users)
aegis-quickstart

# Quick mode with defaults
aegis-quickstart --no-interactive --project-name my-service --examples
```

**Generated Output**:
- Complete DDD project structure
- Example handlers and test clients
- Docker and Docker Compose configuration
- Kubernetes Helm charts
- Development automation (Makefile)
- Pre-commit hooks and CI/CD setup

### 2. `aegis-bootstrap` - Direct Project Creation

**Purpose**: Fast, scriptable project creation for experienced developers

**Features**:
- Command-line driven (no interaction)
- Template selection (enterprise_ddd only currently)
- Environment targeting (local, docker, kubernetes)
- Configurable options for tests, Docker, K8s

**Usage**:
```bash
# Basic project creation
aegis-bootstrap --project-name my-service --template enterprise_ddd --output-dir ./

# With Kubernetes manifests
aegis-bootstrap --project-name my-service --include-k8s --environment kubernetes

# Complete example
aegis-bootstrap \
  --project-name payment-service \
  --template enterprise_ddd \
  --service-name payment-service \
  --nats-url nats://nats:4222 \
  --environment kubernetes \
  --output-dir ./ \
  --include-tests \
  --include-docker \
  --include-k8s
```

### 3. `aegis-validate` - Configuration Validator

**Purpose**: Comprehensive validation and troubleshooting tool

**Validation Capabilities**:
- **Service Name**: Format validation and naming conventions
- **Project Structure**: Essential files and recommended directories
- **Configuration Files**: `pyproject.toml`, `.env` validation
- **NATS Connectivity**: Connection testing and health checks
- **Docker Setup**: Dockerfile validation and Docker installation
- **Kubernetes**: Helm chart validation and kubectl availability
- **Environment Detection**: Auto-detection of local/docker/k8s

**Usage**:
```bash
# Basic validation
aegis-validate --service-name my-service

# With NATS connection testing
aegis-validate --service-name my-service --nats-url nats://localhost:4222

# Environment-specific validation
aegis-validate --service-name my-service --environment kubernetes

# JSON output for automation
aegis-validate --service-name my-service --json
```

**Output Example**:
```
✓ Configuration Valid

Validation Issues:
Level    Category  Message                     Resolution
INFO     PROJECT   Missing recommended dir     Consider adding domain directory
WARNING  CONFIG    Missing .env file          Copy .env.example to .env

Diagnostics:
• detected_environment: local
• docker_installed: true
• docker_python: 3.13

Recommendations:
• Configuration looks good! Ready to deploy
```

### 4. `aegis-test` - Test Runner

**Purpose**: Unified test execution with coverage reporting

**Features**:
- Multiple test types (unit, integration, e2e, all)
- Coverage reporting and thresholds
- Pytest integration with custom markers
- Rich console output with progress

**Usage**:
```bash
# Run all tests with coverage
aegis-test --test-type all --coverage

# Unit tests only
aegis-test --test-type unit --verbose

# With minimum coverage threshold
aegis-test --test-type all --min-coverage 85 --coverage
```

## Code Generation Capabilities

### 1. **Complete Project Structure**

The generator creates a full enterprise-ready project:

```
my-service/
├── domain/                 # Domain-Driven Design Core
│   ├── entities.py        # Business entities with behavior
│   ├── value_objects.py   # Immutable value types
│   ├── repositories.py    # Data access contracts
│   ├── services.py        # Domain logic coordination
│   └── events.py         # Domain events
├── application/           # Use Case Layer
│   ├── commands.py       # CQRS command definitions
│   ├── queries.py        # CQRS query definitions
│   ├── handlers.py       # Command/query handlers with RPC examples
│   └── dto.py           # Data transfer objects
├── infra/                # Infrastructure Layer
│   ├── adapters.py      # External service adapters (business-specific)
│   ├── persistence.py   # Repository implementations using SDK
│   ├── messaging.py     # Event publishing using SDK
│   └── cache.py         # Caching layer using SDK KV store
├── crossdomain/          # Anti-Corruption Layer
│   ├── translators.py   # Data format translators
│   └── anti_corruption.py # External system facades
├── app_types/            # Type Definitions
│   ├── dto.py           # Shared DTOs
│   ├── interfaces.py    # Contract definitions
│   └── enums.py         # Enumeration types
├── pkg/                  # Utilities (business-specific only)
│   ├── utils.py         # Domain-specific helpers
│   ├── validators.py    # Business validation rules
│   └── helpers.py       # Utility functions
├── tests/                # Test Suite
│   ├── unit/            # Unit tests for each layer
│   └── integration/     # Integration tests
├── k8s/                  # Kubernetes Deployment
│   ├── templates/       # Helm templates
│   ├── Chart.yaml       # Helm metadata
│   ├── values.yaml      # Default configuration
│   ├── values-dev.yaml  # Development overrides
│   └── values-prod.yaml # Production overrides
├── main.py              # Service entry point (40-80 lines)
├── Dockerfile           # Multi-stage container build
├── docker-compose.yml   # Local development stack
├── Makefile            # DevOps automation
├── pyproject.toml      # Python project configuration
├── requirements.txt    # Pip compatibility
├── .env.example        # Environment template
├── .gitignore          # Git exclusions
├── .python-version     # Python version for uv
└── README.md           # Project documentation
```

### 2. **Smart Code Generation**

The generator produces **context-aware, production-ready code**:

#### **main.py** - Optimized Service Entry Point
```python
# Generated main.py - Uses SDK Service class (not manual infrastructure)
async def main():
    # Step 1: Connect to NATS
    nats = NATSAdapter()
    await nats.connect(nats_url)

    # Step 2: Create SDK Service (handles ALL infrastructure)
    service = Service(
        service_name=config.service_name,
        message_bus=nats,
        instance_id=config.instance_id,
        service_registry=registry,
        heartbeat_interval=10.0,  # SDK handles heartbeat automatically
        enable_registration=True   # SDK handles registration automatically
    )

    # Step 3: Register business handlers
    await service.register_rpc_method("echo", handle_echo)

    # Step 4: Start service - SDK handles everything!
    await service.start()
```

#### **handlers.py** - RPC Integration Examples
```python
# Generated with proper RPC call examples
class CommandHandler:
    async def handle_create_order(self, command) -> str:
        # Step 1: Check inventory via RPC (external service)
        inventory_request = RPCRequest(
            method="check_availability",
            params={"product_id": command.product_id},
            target="inventory-service"
        )

        # SDK handles all serialization automatically!
        inventory_response = await self._nats.call_rpc(inventory_request)

        # Step 2: Domain logic...
        # Step 3: Process payment via RPC...
```

#### **Educational Infrastructure Files**
The generator creates infrastructure files with educational content that **warns against reimplementing SDK functionality**:

```python
# Generated infra/adapters.py
"""
⚠️ IMPORTANT: Most infrastructure adapters are NOT needed!

The AegisSDK already provides:
✅ NATSAdapter - Message bus
✅ SimpleLogger - Logging
✅ KVServiceRegistry - Service registry
✅ Service - Complete service infrastructure

You should ONLY create adapters for:
1. External APIs specific to your business
2. Custom databases not covered by SDK
3. Third-party services unique to your domain
"""
```

### 3. **DevOps Automation**

#### **Comprehensive Makefile**
```makefile
# Generated Makefile with full DevOps pipeline
.PHONY: deploy-to-kind
deploy-to-kind: docker-build kind-load helm-install
	@echo "✅ Deployment complete! Check: kubectl get pods -n aegis-trader"

.PHONY: docker-build
docker-build: test-local  ## Build with version tags and proxy support
	@VERSION=$$(date +%Y%m%d-%H%M%S); \
	docker build --build-arg HTTP_PROXY="$$HTTP_PROXY" \
		-t my-service:$$VERSION \
		-f Dockerfile "$$AEGIS_ROOT"
```

#### **Kubernetes Helm Charts**
Complete Helm charts with:
- **Production-ready templates** with proper resource limits
- **Multi-environment support** (dev, staging, prod)
- **Health check configuration** (disabled by default to prevent crashes)
- **Ingress and service mesh ready**
- **ConfigMap and secret management**

#### **Docker Configuration**
- **Multi-stage builds** for optimization
- **Proxy support** for corporate environments
- **uv package manager** integration
- **Python 3.13** base images
- **Security best practices**

## Project Scaffolding Features

### 1. **Rapid Development Workflow**

The scaffolding enables this development flow:

```bash
# 1. Create project (5 seconds)
aegis-bootstrap --project-name payment-service --template enterprise_ddd --output-dir ./

# 2. Navigate and setup (30 seconds)
cd payment-service
uv venv && uv pip install -e .

# 3. Validate locally (15 seconds)
make test-local

# 4. Deploy to Kubernetes (3 minutes)
make deploy-to-kind

# 5. Verify deployment (instant)
kubectl get pods -n aegis-trader
```

### 2. **Environment Flexibility**

Projects are generated with support for multiple deployment targets:

- **Local Development**: Docker Compose with NATS
- **Kind/Minikube**: Local Kubernetes testing
- **Cloud Kubernetes**: Production-ready Helm charts
- **CI/CD Integration**: GitHub Actions templates (optional)

### 3. **Package Manager Support**

Full support for modern Python package management:

- **uv** (recommended): Fast, modern Python package manager
- **pip** (fallback): Traditional package management
- **Virtual environment** management
- **Dependency locking** with `uv.lock` or `requirements.txt`

## Integration with AegisSDK

### 1. **Dependency Relationship**

```toml
# pyproject.toml - aegis-sdk-dev depends on aegis-sdk
[project]
dependencies = [
    "aegis-sdk",  # Core SDK functionality
    "click>=8.0.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
]

[tool.uv.sources]
aegis-sdk = { path = "../aegis-sdk" }  # Local development
```

### 2. **SDK Component Usage**

Generated projects leverage these AegisSDK components:

#### **Core Service Infrastructure**
```python
# Generated code uses these SDK classes
from aegis_sdk.application.service import Service, ServiceConfig
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
```

#### **Domain Models and Patterns**
```python
# SDK provides these domain abstractions
from aegis_sdk.domain.models import RPCRequest
from aegis_sdk.application.use_cases import RPCCallUseCase
from aegis_sdk.domain.services import MessageRoutingService
```

### 3. **Anti-Pattern Prevention**

The generated code includes **extensive warnings** against reimplementing SDK functionality:

- **96% code reduction** achieved by using SDK Service class
- **Educational comments** explaining what NOT to implement
- **Best practice examples** for proper SDK usage
- **References to SDK documentation** for advanced patterns

### 4. **Extension Points**

While discouraging reimplementation, the templates show proper SDK extension:

```python
# Extending Service class (not replacing it)
class MyCustomService(Service):
    async def on_start(self):
        """Custom startup logic."""
        await super().on_start()
        # Add custom initialization

# Implementing SDK ports (not custom adapters)
class MyBusinessAdapter(ExternalServicePort):
    """Business-specific external service integration."""
    # Only for business-specific external APIs
```

## Usage Examples and Workflows

### 1. **New Developer Onboarding**

Complete workflow for new team members:

```bash
# Step 1: Install aegis-sdk-dev
pip install aegis-sdk-dev

# Step 2: Create first service with wizard
aegis-quickstart
# Follow interactive prompts...

# Step 3: Explore generated code
cd my-first-service
code .  # Open in VS Code

# Step 4: Run locally
make run

# Step 5: Test the service
python client.py  # Generated test client

# Step 6: Deploy to Kind
make deploy-to-kind
```

### 2. **Experienced Developer Workflow**

Fast track for experienced developers:

```bash
# One-line project creation
aegis-bootstrap --project-name user-service --template enterprise_ddd --include-k8s

# Quick deployment pipeline
cd user-service
make deploy-to-kind

# Validate configuration
aegis-validate --service-name user-service --nats-url nats://localhost:4222
```

### 3. **CI/CD Integration**

Generated projects include automation-ready configurations:

```bash
# Validate in CI
aegis-validate --service-name $SERVICE_NAME --json --environment kubernetes

# Build and test pipeline
make test-local && make docker-build && make helm-upgrade
```

### 4. **Multi-Service Development**

Create multiple coordinated services:

```bash
# Create inventory service
aegis-bootstrap --project-name inventory-service --template enterprise_ddd

# Create order service with RPC calls to inventory
aegis-bootstrap --project-name order-service --template enterprise_ddd

# Generated handlers.py includes proper RPC integration examples
```

## Installation and Setup Instructions

### 1. **System Requirements**

- **Python 3.13+** (recommended, 3.11+ supported)
- **uv** (recommended) or pip
- **Docker** (for containerization)
- **kubectl** (for Kubernetes deployment)
- **Helm** (for K8s package management)
- **Kind** (for local K8s testing)

### 2. **Installation Methods**

#### **Method 1: From Source (Development)**
```bash
# Clone the repository
git clone <aegis-trader-repo>
cd AegisTrader/packages/aegis-sdk-dev

# Install with uv (recommended)
uv venv
source .venv/bin/activate  # Linux/Mac
uv pip install -e .

# Or install with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

#### **Method 2: Via Package Manager**
```bash
# When published to PyPI
pip install aegis-sdk-dev

# With uv
uv pip install aegis-sdk-dev
```

### 3. **Verify Installation**

```bash
# Check CLI commands are available
aegis-bootstrap --help
aegis-quickstart --help
aegis-validate --help
aegis-test --help

# Test with a sample project
aegis-bootstrap --project-name test-service --template enterprise_ddd
cd test-service
make test-local
```

### 4. **Environment Setup**

#### **Corporate Proxy Configuration**
For corporate environments, create `.env` in project root:

```bash
# .env file for proxy support
HTTP_PROXY=http://your-proxy:port
HTTPS_PROXY=http://your-proxy:port
NO_PROXY=localhost,127.0.0.1,nats
```

#### **Kubernetes Setup (Local)**
```bash
# Install and configure Kind
go install sigs.k8s.io/kind@latest
kind create cluster --name aegis-local

# Create namespace
kubectl create namespace aegis-trader

# Install NATS for testing
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm install nats nats/nats -n aegis-trader
```

### 5. **Development Environment**

For contributing to `aegis-sdk-dev`:

```bash
# Install with development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
black .
mypy .

# Build documentation
cd docs && make html
```

## Advanced Configuration

### 1. **Template Customization**

The `SimpleProjectGenerator` can be extended for custom templates:

```python
# Custom template generator
class MyCustomGenerator(SimpleProjectGenerator):
    def _generate_file_content(self, file_path: str, description: str, config: BootstrapConfig) -> str:
        # Custom content generation logic
        if "my_custom_file.py" in file_path:
            return self._generate_custom_content(config)
        return super()._generate_file_content(file_path, description, config)
```

### 2. **Validation Rules Extension**

Add custom validation rules:

```python
# Custom validator
class MyConfigValidator(ConfigValidator):
    async def _check_custom_requirements(self, service_name: str, result: ValidationResult) -> None:
        # Custom validation logic
        pass
```

### 3. **CLI Command Extension**

Add custom CLI commands:

```python
# New CLI command
@click.command()
def my_command():
    """Custom command for specific needs."""
    pass
```

## Relationship to Main AegisSDK

### 1. **Separation of Concerns**

- **`aegis-sdk`**: Runtime framework for microservices
  - Service infrastructure (lifecycle, heartbeat, registration)
  - NATS messaging and KV storage
  - Service discovery and health monitoring
  - Domain abstractions and ports

- **`aegis-sdk-dev`**: Development-time tooling
  - Project scaffolding and code generation
  - CLI tools for creation and validation
  - DevOps automation and deployment
  - Templates and best practices

### 2. **Dependency Flow**

```
aegis-sdk-dev  (development tooling)
    ↓ depends on
aegis-sdk      (runtime framework)
    ↓ depends on
nats-py, pydantic, etc. (external libraries)
```

### 3. **Generated Code Dependencies**

Projects created by `aegis-sdk-dev` depend on `aegis-sdk`:

```toml
# Generated pyproject.toml
[project]
dependencies = [
    "aegis-sdk",  # Runtime dependency
    "pydantic>=2.0.0",
    "python-dateutil>=2.8.0",
]
```

### 4. **Best Practices Enforcement**

`aegis-sdk-dev` enforces proper `aegis-sdk` usage:

- **Prevents reimplementation** of SDK components
- **Provides educational warnings** in generated code
- **Shows correct patterns** for SDK extension
- **Reduces boilerplate** by leveraging SDK infrastructure

---

## Summary

**AegisSDK Development Tools** transforms microservice development from a complex, error-prone process into a streamlined, production-ready workflow. By generating optimized code that properly leverages the AegisSDK infrastructure, it enables teams to:

- **Focus on business logic** rather than infrastructure
- **Deploy production-ready services** in minutes
- **Follow enterprise architecture patterns** automatically
- **Avoid common anti-patterns** and code duplication
- **Scale development teams** with consistent, validated patterns

The toolkit represents a mature approach to developer productivity, combining code generation, validation, and automation to deliver a world-class microservice development experience.
