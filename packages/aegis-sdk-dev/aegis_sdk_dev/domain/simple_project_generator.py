"""Simple project generator using data-driven templates."""

import os

from aegis_sdk_dev.domain.models import BootstrapConfig


class SimpleProjectGenerator:
    """Generate projects from simple template definitions."""

    def __init__(self, template_generator=None):
        """Initialize with optional template generator for enterprise DDD templates."""
        self._template_generator = template_generator

    def generate_project(self, config: BootstrapConfig) -> dict[str, str]:
        """Generate project files from template."""
        files = {}
        base_dir = f"{config.output_dir}/{config.project_name}"

        # Define enterprise DDD template inline
        template = {
            "files": {
                # Domain layer
                "domain/__init__.py": "Domain layer",
                "domain/entities.py": "Domain entities",
                "domain/value_objects.py": "Value objects",
                "domain/repositories.py": "Repository interfaces",
                "domain/services.py": "Domain services",
                "domain/events.py": "Domain events",
                # Application layer
                "application/__init__.py": "Application layer",
                "application/commands.py": "CQRS commands",
                "application/queries.py": "CQRS queries",
                "application/handlers.py": "Command and query handlers",
                "application/dto.py": "Application DTOs",
                # Infrastructure layer
                "infra/__init__.py": "Infrastructure layer",
                "infra/persistence.py": "Persistence implementation",
                "infra/messaging.py": "Messaging implementation",
                "infra/adapters.py": "External service adapters",
                "infra/cache.py": "Caching layer",
                # Cross-domain layer
                "crossdomain/__init__.py": "Anti-corruption layer",
                "crossdomain/translators.py": "Data translators",
                "crossdomain/anti_corruption.py": "Anti-corruption facades",
                "crossdomain/adapters.py": "Bounded context adapters",
                # Package layer
                "pkg/__init__.py": "Utility functions",
                "pkg/utils.py": "General utilities",
                "pkg/validators.py": "Validation functions",
                "pkg/helpers.py": "Helper functions",
                # Types layer
                "app_types/__init__.py": "Type definitions",
                "app_types/dto.py": "Data transfer objects",
                "app_types/interfaces.py": "Interface definitions",
                "app_types/enums.py": "Enumerations",
                # Tests
                "tests/__init__.py": "Test suite",
                "tests/conftest.py": "Pytest configuration",
                "tests/unit/test_domain.py": "Domain unit tests",
                "tests/unit/test_application.py": "Application unit tests",
                "tests/integration/test_service.py": "Service integration tests",
                # Configuration
                "main.py": "Application entry point",
                "requirements.txt": "Python dependencies",
                "pyproject.toml": "Project configuration",
                ".env.example": "Environment variables example",
                ".python-version": "Python version for uv",
                ".gitignore": "Git ignore patterns",
                "README.md": "Project documentation",
                "Makefile": "Common development tasks",
                # Docker
                "Dockerfile": "Docker image definition",
                ".dockerignore": "Docker ignore patterns",
                "docker-compose.yml": "Docker Compose configuration",
                # Kubernetes/Helm
                "k8s/Chart.yaml": "Helm chart metadata",
                "k8s/values.yaml": "Helm default values",
                "k8s/values-dev.yaml": "Development environment values",
                "k8s/values-prod.yaml": "Production environment values",
                "k8s/templates/deployment.yaml": "Kubernetes deployment",
                "k8s/templates/service.yaml": "Kubernetes service",
                "k8s/templates/configmap.yaml": "Kubernetes configmap",
                "k8s/templates/ingress.yaml": "Kubernetes ingress",
                "k8s/templates/serviceaccount.yaml": "Kubernetes service account",
                "k8s/templates/_helpers.tpl": "Helm template helpers",
                "k8s/README.md": "Kubernetes deployment documentation",
            }
        }

        # Create all files with simple descriptive content
        for file_path, description in template.get("files", {}).items():
            full_path = f"{base_dir}/{file_path}"
            content = self._generate_file_content(file_path, description, config)
            files[full_path] = content

            # If we just created .env.example, also create .env from it
            if file_path == ".env.example":
                env_path = f"{base_dir}/.env"
                files[env_path] = content.replace(
                    "# Environment variables example",
                    "# Environment variables (auto-copied from .env.example)",
                )

        return files

    def _generate_file_content(
        self, file_path: str, description: str, config: BootstrapConfig
    ) -> str:
        """Generate file content based on file type and description."""
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1]

        # Check if we should use custom template methods for enterprise DDD content
        if config.template.value == "enterprise_ddd":
            # Map file names to generator methods
            method_mapping = {
                "entities.py": "generate_domain_entities",
                "value_objects.py": "generate_domain_value_objects",
                "repositories.py": "generate_domain_repositories",
                "commands.py": "generate_commands",
                "queries.py": "generate_queries",
                "handlers.py": "generate_handlers",
                "persistence.py": "generate_persistence",
                "messaging.py": "generate_messaging",
                "translators.py": "generate_translators",
                "anti_corruption.py": "generate_anti_corruption",
                "utils.py": "generate_utils",
                "validators.py": "generate_validators",
                "dto.py": "generate_dto",
                "interfaces.py": "generate_interfaces",
            }

            if file_name in method_mapping:
                method_name = method_mapping[file_name]
                # First try self, then fall back to injected template generator
                if hasattr(self, method_name):
                    method = getattr(self, method_name)
                    return method(config)
                elif self._template_generator and hasattr(self._template_generator, method_name):
                    method = getattr(self._template_generator, method_name)
                    return method(config)

        # Python files
        if file_ext == ".py":
            if file_name == "__init__.py":
                return f'"""{description} for {config.project_name}."""\n'
            elif file_name == "main.py":
                return f'''"""Main entry point for {config.project_name}.

This service uses the AegisSDK Service class which provides:
- Automatic service registration and discovery
- Built-in heartbeat management
- Lifecycle management (start/stop/health)
- RPC method registration
- Signal handling

No need to reimplement these features - the SDK handles everything!
"""

import asyncio
import logging
import os
import signal
from datetime import datetime, timezone

# Import AegisSDK components - these provide all infrastructure
from aegis_sdk.application.service import Service, ServiceConfig
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger

# Import your business logic (if using DDD)
# from application.use_cases import YourUseCase
# from domain.services import YourDomainService

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class {config.project_name.replace("-", "_").title().replace("_", "")}Service:
    """Service implementation using SDK Service class."""

    def __init__(self):
        """Initialize the service."""
        self.service = None
        self.nats = None

        # Initialize your domain services here (if using DDD)
        # self.domain_service = YourDomainService()
        # self.use_case = YourUseCase(self.domain_service)

    async def setup_handlers(self, service: Service) -> None:
        """Register RPC handlers with the SDK service.

        The SDK Service class provides:
        - Automatic request/response handling
        - Error management
        - Serialization/deserialization
        """

        async def handle_ping(params: dict) -> dict:
            """Health check endpoint - always include this."""
            return {{"pong": True, "timestamp": params.get("timestamp")}}

        async def handle_health(params: dict) -> dict:
            """Health status endpoint - always include this."""
            return {{
                "status": "healthy",
                "service": self.service_name,
                "instance_id": self.instance_id,
                "version": self.version
            }}

        # TODO: Add your business logic handlers here
        # async def handle_your_method(params: dict) -> dict:
        #     result = await self.use_case.execute(params)
        #     return result

        # Register handlers with SDK service
        await service.register_rpc_method("ping", handle_ping)
        await service.register_rpc_method("health", handle_health)
        # await service.register_rpc_method("your_method", handle_your_method)

        logger.info(f"Registered RPC handlers for {{self.service_name}}")

    async def run(self) -> None:
        """Run the service using SDK Service class.

        The SDK handles:
        - Service lifecycle (starting, running, stopping)
        - Automatic heartbeats (no manual implementation needed!)
        - Service registration (no manual KV operations needed!)
        - Graceful shutdown
        """
        try:
            # Configuration
            self.service_name = os.getenv("SERVICE_NAME", "{config.project_name}")
            nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
            self.version = os.getenv("SERVICE_VERSION", "1.0.0")
            self.instance_id = os.getenv(
                "SERVICE_INSTANCE_ID",
                f"{{self.service_name}}-{{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}}"
            )

            logger.info(f"Starting {{self.service_name}} (instance: {{self.instance_id}}, version: {{self.version}})")

            # Step 1: Connect to NATS
            self.nats = NATSAdapter()
            await self.nats.connect(nats_url)
            logger.info("Connected to NATS")

            # Step 2: Setup KV store for service registry
            kv_store = NATSKVStore(self.nats)
            await kv_store.connect("service_registry")
            registry = KVServiceRegistry(kv_store=kv_store)

            # Step 3: Create SDK Service (handles ALL infrastructure!)
            config = ServiceConfig(
                service_name=self.service_name,
                instance_id=self.instance_id,
                version=self.version,
                heartbeat_interval=10.0,  # SDK handles heartbeat automatically!
                registry_ttl=30.0,
                enable_registration=True  # SDK handles registration automatically!
            )

            self.service = Service(
                service_name=config.service_name,
                message_bus=self.nats,
                instance_id=config.instance_id,
                version=config.version,
                service_registry=registry,
                logger=SimpleLogger(self.service_name),
                heartbeat_interval=config.heartbeat_interval,
                registry_ttl=config.registry_ttl,
                enable_registration=config.enable_registration
            )

            # Step 4: Setup your business logic handlers
            await self.setup_handlers(self.service)

            # Step 5: Start service - SDK handles EVERYTHING!
            # - Lifecycle management
            # - Signal handling (SIGTERM, SIGINT)
            # - Automatic heartbeats
            # - Service registration
            # - Error recovery
            await self.service.start()
            logger.info(f"{{self.service_name}} started successfully")

            # Keep running until shutdown
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Service cancelled")
        except Exception as e:
            logger.error(f"Service failed: {{e}}", exc_info=True)
            raise
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        logger.info("Starting cleanup...")

        # Stop SDK service (handles all cleanup)
        if self.service:
            await self.service.stop()
            logger.info("SDK service stopped")

        # Disconnect NATS
        if self.nats:
            await self.nats.disconnect()
            logger.info("NATS disconnected")

        logger.info("Cleanup complete")


async def main():
    """Main entry point."""
    service = {config.project_name.replace("-", "_").title().replace("_", "")}Service()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await service.run()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted")
'''
            elif "test_" in file_name:
                return f'''"""{description} for {config.project_name}."""

import pytest


def test_placeholder():
    """Placeholder test."""
    assert True
'''
            elif file_name == "adapters.py" and "infra" in file_path:
                return f'''"""{description} - Educational Template.

⚠️ IMPORTANT: Most infrastructure adapters are NOT needed!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The AegisSDK already provides these components:
✅ aegis_sdk.infrastructure.nats_adapter.NATSAdapter - Message bus
✅ aegis_sdk.infrastructure.simple_logger.SimpleLogger - Logging
✅ aegis_sdk.infrastructure.kv_service_registry.KVServiceRegistry - Service registry
✅ aegis_sdk.application.service.Service - Complete service infrastructure

You should ONLY create adapters for:
1. External APIs specific to your business (e.g., payment gateways)
2. Custom databases not covered by SDK
3. Third-party services unique to your domain

❌ DON'T create adapters for:
- Logging (use SimpleLogger)
- NATS messaging (use NATSAdapter directly)
- Service registry (use KVServiceRegistry)
- Configuration (use environment variables)

Example of a VALID adapter (business-specific):
"""

from typing import Dict, Any
import httpx

class PaymentGatewayAdapter:
    """Adapter for external payment service - this is business-specific."""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    async def process_payment(self, amount: float, currency: str) -> Dict[str, Any]:
        """Process payment through external gateway."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{{self.api_url}}/payments",
                headers={{"Authorization": f"Bearer {{self.api_key}}"}},
                json={{"amount": amount, "currency": currency}}
            )
            return response.json()

# TODO: Add your business-specific adapters here
# Remember: Don't wrap SDK components - use them directly!
'''
            elif file_name == "persistence.py" and "infra" in file_path:
                return f'''"""{description} - Educational Template.

⚠️ NOTE: The SDK provides KV store persistence!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For simple persistence needs, use:
✅ aegis_sdk.infrastructure.nats_kv_store.NATSKVStore - Key-value storage

Example using SDK's KV store:
"""

from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter

class UserRepository:
    """Example repository using SDK's KV store.

    Note: KV store accepts string values. For complex objects,
    the SDK internally handles serialization with msgpack.
    """

    def __init__(self, nats_adapter: NATSAdapter):
        self.kv_store = NATSKVStore(nats_adapter)

    async def connect(self):
        """Connect to KV bucket."""
        await self.kv_store.connect("users")

    async def save(self, user_id: str, user_data: dict):
        """Save user data."""
        # For simple string/bytes, pass directly
        # For complex objects, convert to string representation
        await self.kv_store.put(
            key=f"user:{{user_id}}",
            value=str(user_data),  # KV store handles the rest
            ttl=3600  # Optional TTL in seconds
        )

    async def get(self, user_id: str) -> dict:
        """Get user data."""
        result = await self.kv_store.get(f"user:{{user_id}}")
        if result and result.value:
            # Parse the stored string representation
            return eval(result.value)  # Or use ast.literal_eval for safety
        return None

# TODO: Implement your repository using SDK's KV store
# For complex queries, consider using a proper database
'''
            elif file_name == "messaging.py" and "infra" in file_path:
                return f'''"""{description} - Educational Template.

⚠️ IMPORTANT: Use SDK's Service class for messaging!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The SDK Service class already handles:
✅ RPC method registration
✅ Request/response patterns
✅ Pub/sub messaging
✅ Error handling
✅ Serialization

You DON'T need to implement messaging infrastructure!

Example using SDK Service for messaging:
"""

# This file is usually NOT needed!
# Use the Service class in main.py instead:

# In your main.py:
# await service.register_rpc_method("my_method", handle_my_method)

# For pub/sub patterns:
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.domain.events import Event

async def publish_domain_event(nats: NATSAdapter, event: Event):
    """Example of publishing a domain event using SDK.

    The SDK handles ALL serialization automatically with msgpack!
    You don't need to manually serialize anything.
    """
    # SDK automatically serializes the event with msgpack
    await nats.publish_event(event)

# TODO: Most messaging should be handled through Service class
# Only add custom messaging for special patterns not covered by RPC
'''
            elif file_name == "cache.py" and "infra" in file_path:
                return f'''"""{description} - Educational Template.

💡 TIP: Consider if you really need caching!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The SDK's KV store can be used for caching with TTL:
✅ aegis_sdk.infrastructure.nats_kv_store.NATSKVStore

Example simple cache using SDK:
"""

from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from typing import Optional, Any

class SimpleCache:
    """Simple cache implementation using SDK's KV store.

    Note: The SDK uses msgpack for RPC serialization.
    KV store accepts string values for simplicity.
    """

    def __init__(self, kv_store: NATSKVStore):
        self.kv_store = kv_store

    async def get(self, key: str) -> Optional[str]:
        """Get cached value as string."""
        result = await self.kv_store.get(f"cache:{{key}}")
        if result and result.value:
            return result.value
        return None

    async def set(self, key: str, value: str, ttl_seconds: int = 300):
        """Set cached value with TTL."""
        await self.kv_store.put(
            key=f"cache:{{key}}",
            value=value,  # Store as string
            ttl=ttl_seconds
        )

# TODO: Implement caching if really needed
# Consider: Is the performance gain worth the complexity?
'''
            elif file_name == "utils.py" and "pkg" in file_path:
                return rf'''"""{description} - General utilities.

⚠️ IMPORTANT: DO NOT implement serialization here!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The SDK handles ALL serialization automatically:
- RPC: Uses msgpack by default
- Events: Automatic serialization
- You work with Python objects directly

This file is for business-specific utilities only.
"""

from typing import Any, Optional
import re


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{{2,}}$'
    return bool(re.match(pattern, email))


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency string."""
    symbols = {{"USD": "$", "EUR": "€", "GBP": "£"}}
    symbol = symbols.get(currency, currency)
    return f"{{symbol}}{{amount:,.2f}}"


def sanitize_input(text: str) -> str:
    """Sanitize user input."""
    # Remove control characters
    return ''.join(char for char in text if char.isprintable())


# Add your business-specific utilities here
# Remember: NO serialization utilities needed!
'''
            else:
                return f'''"""{description} for {config.project_name}."""

# TODO: Implement {description.lower()}
'''

        # Requirements file (for compatibility, but uv uses pyproject.toml)
        elif file_name == "requirements.txt":
            return """# Dependencies are managed in pyproject.toml
# This file is kept for compatibility
# Use: uv pip install -e .
"""

        # Docker files
        elif file_name == "Dockerfile":  # nosec B608
            return f"""# {description}
# Use Python 3.13+ as base image
FROM python:3.13-slim

# Accept proxy build arguments
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Set working directory
WORKDIR /app

# Set environment variables for Python and uv
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PYTHONPATH=/app:/packages \\
    UV_CACHE_DIR=/tmp/uv-cache

# Install system dependencies and uv (this layer is cached)
RUN if [ -n "$HTTP_PROXY" ]; then \\
      export http_proxy=$HTTP_PROXY && \\
      export https_proxy=$HTTPS_PROXY && \\
      export HTTP_PROXY=$HTTP_PROXY && \\
      export HTTPS_PROXY=$HTTPS_PROXY; \\
    fi && \\
    apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    curl \\
    && curl -LsSf https://astral.sh/uv/install.sh | sh \\
    && mv /root/.local/bin/uv /usr/local/bin/ \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (these rarely change)
RUN if [ -n "$HTTP_PROXY" ]; then \\
      export http_proxy=$HTTP_PROXY && \\
      export https_proxy=$HTTPS_PROXY && \\
      export HTTP_PROXY=$HTTP_PROXY && \\
      export HTTPS_PROXY=$HTTPS_PROXY && \\
      export UV_HTTP_PROXY=$HTTP_PROXY && \\
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \\
    fi && \\
    uv pip install --system --no-cache \\
    pydantic==2.10.0 \\
    python-dateutil==2.8.2

# Copy and install the SDK packages (SDK changes trigger rebuild)
COPY packages/aegis-sdk /packages/aegis-sdk
COPY packages/aegis-sdk-dev /packages/aegis-sdk-dev
RUN if [ -n "$HTTP_PROXY" ]; then \\
      export http_proxy=$HTTP_PROXY && \\
      export https_proxy=$HTTPS_PROXY && \\
      export HTTP_PROXY=$HTTP_PROXY && \\
      export HTTPS_PROXY=$HTTPS_PROXY && \\
      export UV_HTTP_PROXY=$HTTP_PROXY && \\
      export UV_HTTPS_PROXY=$HTTPS_PROXY; \\
    fi && \\
    uv pip install --system --no-cache -e /packages/aegis-sdk && \\
    uv pip install --system --no-cache -e /packages/aegis-sdk-dev

# Copy the specific project directory
# The actual path will be determined at build time
# Build context is always from AEGIS_ROOT
ARG PROJECT_PATH=.
COPY ${{PROJECT_PATH}}/ /app/

# Set environment variables
ENV SERVICE_NAME={config.project_name} \\
    SERVICE_VERSION=1.0.0 \\
    LOG_LEVEL=INFO \\
    ENVIRONMENT=development

# Run the application
CMD ["python", "main.py"]
"""

        elif file_name == ".dockerignore":
            return """*.pyc
__pycache__
.pytest_cache
.coverage
*.egg-info
.git
.venv
# Exclude copied packages from final context (they're already in /tmp/)
aegis-sdk/
aegis-sdk-dev/
"""

        elif file_name == "docker-compose.yml":
            return f"""# {description}
version: '3.8'

services:
  # NATS messaging server with JetStream
  nats:
    image: nats:latest
    container_name: {config.project_name}-nats
    ports:
      - "4222:4222"  # Client connections
      - "8222:8222"  # Monitoring
    command: "-js -m 8222"  # Enable JetStream and monitoring
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "4222"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - {config.project_name}-network

  # Main service
  {config.project_name}:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        # Pass proxy settings from .env during build
        HTTP_PROXY: ${{HTTP_PROXY}}
        HTTPS_PROXY: ${{HTTPS_PROXY}}
        NO_PROXY: ${{NO_PROXY}}
    container_name: {config.project_name}
    depends_on:
      nats:
        condition: service_healthy
    environment:
      # Service configuration
      SERVICE_NAME: {config.project_name}
      NATS_URL: nats://nats:4222
      LOG_LEVEL: ${{LOG_LEVEL:-INFO}}
      ENVIRONMENT: ${{ENVIRONMENT:-development}}
      # Proxy settings for runtime (if needed)
      HTTP_PROXY: ${{HTTP_PROXY}}
      HTTPS_PROXY: ${{HTTPS_PROXY}}
      NO_PROXY: ${{NO_PROXY}}
    ports:
      - "8080:8080"
    volumes:
      - .:/app:ro  # Mount as read-only for security
    networks:
      - {config.project_name}-network
    restart: unless-stopped

networks:
  {config.project_name}-network:
    driver: bridge
"""

        # Kubernetes YAML files (Helm-compatible)
        elif (file_ext == ".yaml" or file_ext == ".tpl") and "k8s" in file_path:
            # 处理 values 文件
            if "values-dev" in file_name:
                return f"""# Development environment values for {config.project_name}
# Override default values for development

replicaCount: 1

image:
  pullPolicy: Always

resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 50m
    memory: 128Mi

logLevel: DEBUG

# Development NATS
nats:
  url: "nats://localhost:4222"
"""
            elif "values-prod" in file_name:
                return f"""# Production environment values for {config.project_name}
# Override default values for production

replicaCount: 3

image:
  pullPolicy: IfNotPresent

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi

logLevel: INFO

# Production NATS cluster
nats:
  url: "nats://nats.production.svc.cluster.local:4222"

# Enable ingress for production
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: {config.project_name}.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: {config.project_name}-tls
      hosts:
        - {config.project_name}.example.com
"""
            elif "serviceaccount" in file_name:
                return f"""{{{{- if .Values.serviceAccount.create -}}}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{{{ include "{config.project_name}.serviceAccountName" . }}}}
  labels:
    {{{{- include "{config.project_name}.labels" . | nindent 4 }}}}
  {{{{- with .Values.serviceAccount.annotations }}}}
  annotations:
    {{{{- toYaml . | nindent 4 }}}}
  {{{{- end }}}}
{{{{- end }}}}
"""
            elif "deployment" in file_name:
                return f"""# {description}
# This template is designed to work with Helm
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{ include "{config.project_name}.fullname" . }}}}
  labels:
    {{{{- include "{config.project_name}.labels" . | nindent 4 }}}}
spec:
  replicas: {{{{ .Values.replicaCount | default 1 }}}}
  selector:
    matchLabels:
      {{{{- include "{config.project_name}.selectorLabels" . | nindent 6 }}}}
  template:
    metadata:
      labels:
        {{{{- include "{config.project_name}.selectorLabels" . | nindent 8 }}}}
    spec:
      containers:
      - name: {{{{ .Chart.Name }}}}
        image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag | default .Chart.AppVersion }}}}"
        imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
        ports:
        - name: http
          containerPort: {{{{ .Values.service.targetPort | default 8080 }}}}
          protocol: TCP
        env:
        - name: NATS_URL
          value: "nats://aegis-trader-nats:4222"
        - name: SERVICE_NAME
          value: "{config.project_name}"
        - name: SERVICE_VERSION
          value: "{{{{ .Chart.AppVersion }}}}"
        - name: SERVICE_INSTANCE_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        {{{{- if .Values.livenessProbe.enabled }}}}
        livenessProbe:
          httpGet:
            path: {{{{ .Values.livenessProbe.path }}}}
            port: http
          initialDelaySeconds: {{{{ .Values.livenessProbe.initialDelaySeconds }}}}
          periodSeconds: {{{{ .Values.livenessProbe.periodSeconds }}}}
          timeoutSeconds: {{{{ .Values.livenessProbe.timeoutSeconds }}}}
          failureThreshold: {{{{ .Values.livenessProbe.failureThreshold }}}}
        {{{{- end }}}}
        {{{{- if .Values.readinessProbe.enabled }}}}
        readinessProbe:
          httpGet:
            path: {{{{ .Values.readinessProbe.path }}}}
            port: http
          initialDelaySeconds: {{{{ .Values.readinessProbe.initialDelaySeconds }}}}
          periodSeconds: {{{{ .Values.readinessProbe.periodSeconds }}}}
          timeoutSeconds: {{{{ .Values.readinessProbe.timeoutSeconds }}}}
          failureThreshold: {{{{ .Values.readinessProbe.failureThreshold }}}}
        {{{{- end }}}}
        resources:
          {{{{- toYaml .Values.resources | nindent 10 }}}}
"""
            elif "service" in file_name:
                return f"""# {description}
# This template is designed to work with Helm
apiVersion: v1
kind: Service
metadata:
  name: {{{{ include "{config.project_name}.fullname" . }}}}
  labels:
    {{{{- include "{config.project_name}.labels" . | nindent 4 }}}}
spec:
  type: {{{{ .Values.service.type }}}}
  ports:
  - port: {{{{ .Values.service.port }}}}
    targetPort: http
    protocol: TCP
    name: http
  selector:
    {{{{- include "{config.project_name}.selectorLabels" . | nindent 4 }}}}
"""
            elif "configmap" in file_name:
                return f"""# {description}
# This template is designed to work with Helm
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{{{ include "{config.project_name}.fullname" . }}}}-config
  labels:
    {{{{- include "{config.project_name}.labels" . | nindent 4 }}}}
data:
  {{{{- range $key, $value := .Values.config }}}}
  {{{{ $key }}}}: {{{{ $value | quote }}}}
  {{{{- end }}}}
"""
            elif "ingress" in file_name:
                return f"""# {description}
# This template is designed to work with Helm
{{{{- if .Values.ingress.enabled -}}}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{{{ include "{config.project_name}.fullname" . }}}}
  labels:
    {{{{- include "{config.project_name}.labels" . | nindent 4 }}}}
  {{{{- with .Values.ingress.annotations }}}}
  annotations:
    {{{{- toYaml . | nindent 4 }}}}
  {{{{- end }}}}
spec:
  {{{{- if .Values.ingress.tls }}}}
  tls:
  {{{{- range .Values.ingress.tls }}}}
  - hosts:
    {{{{- range .hosts }}}}
    - {{{{ . | quote }}}}
    {{{{- end }}}}
    secretName: {{{{ .secretName }}}}
  {{{{- end }}}}
  {{{{- end }}}}
  rules:
  {{{{- range .Values.ingress.hosts }}}}
  - host: {{{{ .host | quote }}}}
    http:
      paths:
      {{{{- range .paths }}}}
      - path: {{{{ .path }}}}
        pathType: {{{{ .pathType }}}}
        backend:
          service:
            name: {{{{ include "{config.project_name}.fullname" $ }}}}
            port:
              number: {{{{ $.Values.service.port }}}}
      {{{{- end }}}}
  {{{{- end }}}}
{{{{- end }}}}
"""
            elif "values" in file_name:
                return f"""# {description}
# Default values for {config.project_name}
# This is a YAML-formatted file.
# Declare variables to be passed into your templates.

replicaCount: 1

image:
  repository: {config.project_name}
  pullPolicy: IfNotPresent
  tag: "latest"

service:
  type: ClusterIP
  port: 80
  targetPort: 8080

ingress:
  enabled: false
  annotations: {{}}
    # kubernetes.io/ingress.class: nginx
    # kubernetes.io/tls-acme: "true"
  hosts:
    - host: {config.project_name}.local
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls: []
  #  - secretName: {config.project_name}-tls
  #    hosts:
  #      - {config.project_name}.local

resources: {{}}
  # limits:
  #   cpu: 100m
  #   memory: 128Mi
  # requests:
  #   cpu: 100m
  #   memory: 128Mi

# Health checks - disabled by default since service may not have HTTP endpoint
livenessProbe:
  enabled: false
  path: /health
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  enabled: false
  path: /health
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3

config:
  app.name: {config.project_name}
  app.env: production

serviceAccount:
  # Specifies whether a service account should be created
  create: false
  # Annotations to add to the service account
  annotations: {{}}
  # The name of the service account to use.
  # If not set and create is true, a name is generated using the fullname template
  name: ""
"""
            elif "Chart" in file_name:
                return f"""# {description}
apiVersion: v2
name: {config.project_name}
description: A Helm chart for {config.project_name}
type: application
version: 0.1.0
appVersion: "1.0.0"
"""
            elif "_helpers" in file_name:
                return f"""# {description}
{{{{/*
Expand the name of the chart.
*/}}}}
{{{{- define "{config.project_name}.name" -}}}}
{{{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Create a default fully qualified app name.
*/}}}}
{{{{- define "{config.project_name}.fullname" -}}}}
{{{{- if .Values.fullnameOverride }}}}
{{{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- $name := default .Chart.Name .Values.nameOverride }}}}
{{{{- if contains $name .Release.Name }}}}
{{{{- .Release.Name | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}
{{{{- end }}}}
{{{{- end }}}}

{{{{/*
Create chart name and version as used by the chart label.
*/}}}}
{{{{- define "{config.project_name}.chart" -}}}}
{{{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Common labels
*/}}}}
{{{{- define "{config.project_name}.labels" -}}}}
helm.sh/chart: {{{{ include "{config.project_name}.chart" . }}}}
{{{{ include "{config.project_name}.selectorLabels" . }}}}
{{{{- if .Chart.AppVersion }}}}
app.kubernetes.io/version: {{{{ .Chart.AppVersion | quote }}}}
{{{{- end }}}}
app.kubernetes.io/managed-by: {{{{ .Release.Service }}}}
{{{{- end }}}}

{{{{/*
Selector labels
*/}}}}
{{{{- define "{config.project_name}.selectorLabels" -}}}}
app.kubernetes.io/name: {{{{ include "{config.project_name}.name" . }}}}
app.kubernetes.io/instance: {{{{ .Release.Name }}}}
{{{{- end }}}}

{{{{/*
Create the name of the service account to use
*/}}}}
{{{{- define "{config.project_name}.serviceAccountName" -}}}}
{{{{- if .Values.serviceAccount.create }}}}
{{{{- default (include "{config.project_name}.fullname" .) .Values.serviceAccount.name }}}}
{{{{- else }}}}
{{{{- default "default" .Values.serviceAccount.name }}}}
{{{{- end }}}}
{{{{- end }}}}
"""
            else:
                return f"# {description}\n# TODO: Configure this resource\n"

        # Configuration files
        elif file_name == "pyproject.toml":
            return f"""# {description}
[project]
name = "{config.project_name}"
version = "0.1.0"
description = "AegisSDK service: {config.project_name}"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "click>=8.0.0",
    "httpx>=0.24.0",
    "python-dateutil>=2.8.0",
    # Note: aegis-sdk will be installed from local copy in Docker
    "aegis-sdk",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["{config.project_name}"]

[tool.ruff]
line-length = 100
target-version = "py313"
select = ["E", "F", "I", "N", "W", "UP"]

[tool.black]
line-length = 100
target-version = ["py313"]

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-v --cov={config.project_name} --cov-report=term-missing"

[tool.uv]
dev-dependencies = [
    "ipython>=8.0.0",
    "ipdb>=0.13.0",
]

[tool.uv.sources]
aegis-sdk = {{ path = "../packages/aegis-sdk" }}
"""

        elif file_name == ".python-version":
            return "3.13\n"

        elif file_name == ".gitignore":
            return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
ENV/
env.bak/
venv.bak/

# uv
.venv/
uv.lock

# Testing
.coverage
.pytest_cache/
htmlcov/
.tox/
.nox/
coverage.xml
*.cover
.hypothesis/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Project
*.log
*.db
*.sqlite
.env
!.env.example

# Build
dist/
build/
*.egg-info/
.eggs/
*.egg

# Docker
*.pid
"""

        elif file_name == ".env.example":
            return f"""# {description}
# Service Configuration
SERVICE_NAME={config.project_name}
SERVICE_VERSION=1.0.0
SERVICE_PORT=8080
ENVIRONMENT=development
LOG_LEVEL=INFO

# NATS Configuration
NATS_URL=nats://localhost:4222
NATS_CLIENT_PORT=4222
NATS_MONITOR_PORT=8222

# Docker build proxy configuration (optional)
# Uncomment and set these if you need proxy for Docker builds
# HTTP_PROXY=http://your-proxy:port
# HTTPS_PROXY=http://your-proxy:port
# NO_PROXY=localhost,127.0.0.1,nats

# Application Settings
DEPLOYMENT_TIMEOUT=300
HEALTH_CHECK_INTERVAL=30
MAX_RETRIES=3

# Feature Flags
ENABLE_METRICS=true
ENABLE_TRACING=false
ENABLE_DEBUG=false
"""

        elif file_name == "Makefile":
            return f"""# Makefile for {config.project_name}
# Common development and deployment tasks

.PHONY: help
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {{FS = ":.*?## "}}; {{printf "  \\033[36m%-20s\\033[0m %s\\n", $$1, $$2}}'

# Environment setup
.PHONY: install
install: ## Install dependencies with uv
	uv pip install -e .

.PHONY: install-dev
install-dev: ## Install with development dependencies
	uv pip install -e ".[dev]"

.PHONY: clean
clean: ## Clean build artifacts and cache
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {{}} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/ .coverage htmlcov/

# Development
.PHONY: run
run: ## Run the service locally
	uv run python main.py

.PHONY: test-local
test-local: ## Test main.py locally (quick validation before Docker build)
	@echo "🧪 Testing main.py locally for errors..."
	@if timeout 3 uv run python main.py 2>&1 | grep -E "(AttributeError|ImportError|TypeError|ModuleNotFoundError|NameError|SyntaxError)" | grep -v "Error during shutdown"; then \\
		echo "❌ Local test failed! Fix errors before building Docker image."; \\
		exit 1; \\
	else \\
		echo "✅ Local test passed (no critical errors detected)"; \\
	fi

.PHONY: dev
dev: ## Run with hot reload (requires watchdog)
	uv run python -m watchdog.auto_restart --directory . --pattern "*.py" --recursive -- python main.py

# Testing
.PHONY: test
test: ## Run all tests
	uv run pytest

.PHONY: test-unit
test-unit: ## Run unit tests only
	uv run pytest tests/unit/

.PHONY: test-integration
test-integration: ## Run integration tests only
	uv run pytest tests/integration/

.PHONY: test-coverage
test-coverage: ## Run tests with coverage report
	uv run pytest --cov={config.project_name} --cov-report=html --cov-report=term

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	uv run ptw -- --testmon

# Code quality
.PHONY: format
format: ## Format code with black and ruff
	uv run black .
	uv run ruff check --fix .

.PHONY: lint
lint: ## Run linting checks
	uv run ruff check .
	uv run mypy .

.PHONY: check
check: lint test ## Run all quality checks

# Docker
.PHONY: docker-build
docker-build: test-local ## Build Docker image with versioned tag (validates code first)
	@VERSION=$$(date +%Y%m%d-%H%M%S); \\
	echo "🔨 Building Docker image {config.project_name}:$$VERSION..."; \\
	# Find .env file with AEGIS_ROOT by searching up the directory tree \\
	ENV_FILE=$$(pwd); \\
	FOUND_ROOT=false; \\
	while [ "$$ENV_FILE" != "/" ]; do \\
		if [ -f "$$ENV_FILE/.env" ]; then \\
			if grep -q "^AEGIS_ROOT=" "$$ENV_FILE/.env" 2>/dev/null; then \\
				FOUND_ROOT=true; \\
				break; \\
			fi; \\
		fi; \\
		ENV_FILE=$$(dirname "$$ENV_FILE"); \\
	done; \\
	if [ "$$FOUND_ROOT" = true ]; then \\
		echo "Loading settings from $$ENV_FILE/.env"; \\
		. "$$ENV_FILE/.env"; \\
		echo "  AEGIS_ROOT: $$AEGIS_ROOT"; \\
		echo "  HTTP_PROXY: $$HTTP_PROXY"; \\
		echo "  HTTPS_PROXY: $$HTTPS_PROXY"; \\
		echo "  NO_PROXY: $$NO_PROXY"; \\
		PROJECT_DIR=$$(pwd); \\
		PROJECT_PATH=$$(echo "$$PROJECT_DIR" | sed "s|$$AEGIS_ROOT/||"); \\
		echo "  PROJECT_PATH: $$PROJECT_PATH"; \\
		docker build --no-cache \\
			--build-arg HTTP_PROXY="$$HTTP_PROXY" \\
			--build-arg HTTPS_PROXY="$$HTTPS_PROXY" \\
			--build-arg NO_PROXY="$$NO_PROXY" \\
			--build-arg PROJECT_PATH="$$PROJECT_PATH" \\
			-t {config.project_name}:$$VERSION \\
			-f Dockerfile "$$AEGIS_ROOT" && \\
		docker tag {config.project_name}:$$VERSION {config.project_name}:latest && \\
		echo "✅ Image built: {config.project_name}:$$VERSION (also tagged as latest)"; \\
	else \\
		echo "Error: No .env file found with AEGIS_ROOT definition"; \\
		exit 1; \\
	fi

.PHONY: docker-run
docker-run: ## Run Docker container
	docker run --rm -p 8080:8080 --env-file .env {config.project_name}:latest

.PHONY: docker-compose-up
docker-compose-up: ## Start services with docker-compose
	docker-compose up -d

.PHONY: docker-compose-down
docker-compose-down: ## Stop services with docker-compose
	docker-compose down

.PHONY: docker-compose-logs
docker-compose-logs: ## Show docker-compose logs
	docker-compose logs -f

# Kind
.PHONY: kind-load
kind-load: ## Load Docker image to kind cluster
	@VERSION=$$(docker images {config.project_name} --format "{{{{.Tag}}}}" | grep -E '^[0-9]{{8}}-[0-9]{{6}}$$' | head -1); \\
	if [ -z "$$VERSION" ]; then \\
		echo "❌ No versioned image found, please run 'make docker-build' first"; \\
		exit 1; \\
	fi; \\
	echo "📦 Loading image {config.project_name}:$$VERSION to kind cluster..."; \\
	docker save {config.project_name}:$$VERSION | docker exec -i aegis-local-control-plane ctr -n k8s.io images import - && \\
	echo "✅ Image loaded to kind: {config.project_name}:$$VERSION"

# Helm (K8s templates are Helm charts, use helm commands for deployment)
.PHONY: helm-install
helm-install: ## Install with Helm
	@VERSION=$$(docker images {config.project_name} --format "{{{{.Tag}}}}" | grep -E '^[0-9]{{8}}-[0-9]{{6}}$$' | head -1); \\
	if [ -z "$$VERSION" ]; then \\
		echo "❌ No versioned image found, please run 'make docker-build' first"; \\
		exit 1; \\
	fi; \\
	helm upgrade --install {config.project_name} ./k8s \\
		--set image.tag=$$VERSION \\
		--set image.repository={config.project_name} \\
		-n aegis-trader

.PHONY: helm-upgrade
helm-upgrade: ## Upgrade Helm deployment
	@VERSION=$$(docker images {config.project_name} --format "{{{{.Tag}}}}" | grep -E '^[0-9]{{8}}-[0-9]{{6}}$$' | head -1); \\
	if [ -z "$$VERSION" ]; then \\
		echo "❌ No versioned image found, please run 'make docker-build' first"; \\
		exit 1; \\
	fi; \\
	helm upgrade {config.project_name} ./k8s \\
		--set image.tag=$$VERSION \\
		--set image.repository={config.project_name} \\
		-n aegis-trader

.PHONY: helm-uninstall
helm-uninstall: ## Uninstall Helm deployment
	helm uninstall {config.project_name} -n aegis-trader

# Combined deployment
.PHONY: deploy-to-kind
deploy-to-kind: docker-build kind-load helm-install ## Build, load to kind, and deploy
	@echo "✅ Deployment complete! Check: kubectl get pods -n aegis-trader"

# Validation
.PHONY: validate
validate: ## Validate environment with aegis-validate
	aegis validate -s {config.project_name}

.PHONY: validate-k8s
validate-k8s: ## Validate Kubernetes environment
	aegis validate --environment kubernetes

# Release
.PHONY: version
version: ## Show current version
	@grep version pyproject.toml | head -1 | cut -d'"' -f2

.PHONY: release
release: check ## Create a new release (runs checks first)
	@echo "Ready for release. Update version in pyproject.toml and create git tag."
"""

        elif file_name == "README.md":
            return f"""# {config.project_name}

{description}

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Setup

### Using uv (recommended)

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"
```

### Using pip

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
pip install -e .
```

## Development

```bash
# Run the application
uv run python main.py

# Run tests
uv run pytest

# Format code
uv run black .
uv run ruff check --fix .

# Type checking
uv run mypy .
```

## Docker

```bash
# Build image
docker build -t {config.project_name} .

# Run container
docker run -p 8080:8080 {config.project_name}
```

## Kubernetes/Helm

```bash
# Deploy with Helm
helm install {config.project_name} ./k8s -f k8s/values.yaml

# Or apply directly
kubectl apply -f k8s/
```
"""

        elif file_name == "config.py":
            return f'''"""{description} for {config.project_name}."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "{config.project_name}"
    app_env: str = "development"
    app_port: int = 8080

    class Config:
        env_file = ".env"


settings = Settings()
'''

        # Default for any other file type
        else:
            return f"# {description}\n# TODO: Implement this file\n"

    def generate_handlers(self, config: BootstrapConfig) -> str:
        """Generate application handlers with RPC examples."""
        return '''"""Command and query handlers with RPC integration examples.

This is the RIGHT place for RPC calls to other services!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ IMPORTANT: The SDK handles ALL serialization automatically!
- RPC uses msgpack by default (NOT JSON)
- You work with Python dicts/objects directly
- Never manually serialize/deserialize
- The SDK handles datetime, complex types, etc.

Application layer coordinates business logic and external services.
"""

from typing import Optional, List, Dict, Any
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.domain.models import RPCRequest
from aegis_sdk.application.use_cases import RPCCallUseCase
from aegis_sdk.domain.services import MessageRoutingService, MetricsNamingService
from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics


class CommandHandler:
    """Handles commands - coordinates domain logic and external services.

    This is where you make RPC calls to other services when needed!
    The SDK handles all serialization/deserialization automatically.
    """

    def __init__(self, repository, event_bus, nats_adapter: NATSAdapter = None):
        self._repository = repository
        self._event_bus = event_bus
        self._nats = nats_adapter  # For RPC calls to other services

        # Optional: Setup RPC use case for production-ready calls
        if self._nats:
            self._rpc_use_case = RPCCallUseCase(
                message_bus=self._nats,
                metrics=InMemoryMetrics(),
                routing_service=MessageRoutingService(),
                naming_service=MetricsNamingService()
            )

    async def handle_create_order(self, command) -> str:
        """Example: Create order with external service calls.

        This shows the PROPER way to call other services via RPC.
        """
        # Step 1: Check inventory via RPC (external service)
        if self._nats:
            inventory_request = RPCRequest(
                method="check_availability",
                params={"product_id": command.product_id, "quantity": command.quantity},
                target="inventory-service"  # Target service name
            )

            # SDK handles all serialization automatically!
            inventory_response = await self._nats.call_rpc(inventory_request)

            if not inventory_response.success:
                raise Exception(f"Inventory check failed: {inventory_response.error}")

            if not inventory_response.result.get("available"):
                raise Exception("Product not available")

        # Step 2: Create order in domain
        # ... your domain logic here ...

        # Step 3: Process payment via RPC (external service)
        if self._nats:
            payment_request = RPCRequest(
                method="process_payment",
                params={
                    "amount": command.amount,
                    "currency": command.currency,
                    "customer_id": command.customer_id
                },
                target="payment-service"
            )

            payment_response = await self._nats.call_rpc(payment_request)

            if not payment_response.success:
                # Compensate: cancel order, restore inventory
                raise Exception(f"Payment failed: {payment_response.error}")

        # Step 4: Save and publish event
        # ... save to repository and publish domain event ...

        return "order_id"

    async def handle_update_status(self, command) -> None:
        """Handle update status command."""
        # Load entity
        # Update status
        # Save changes
        # Publish event
        pass

    async def handle_cancel_order(self, command) -> None:
        """Handle cancel order - may need to call external services."""
        # Coordinate cancellation across services
        pass


class QueryHandler:
    """Handles queries - may aggregate data from multiple services.

    Queries can also make RPC calls to gather data from other services!
    """

    def __init__(self, read_model, nats_adapter: NATSAdapter = None):
        self._read_model = read_model
        self._nats = nats_adapter  # For cross-service queries

    async def handle_get_order_details(self, query) -> Optional[Dict[str, Any]]:
        """Get order with enriched data from other services."""
        # Get local order data
        order = await self._read_model.get_order(query.order_id)

        if order and self._nats:
            # Enrich with customer data via RPC
            customer_request = RPCRequest(
                method="get_customer",
                params={"customer_id": order["customer_id"]},
                target="customer-service"
            )

            customer_response = await self._nats.call_rpc(customer_request)
            if customer_response.success:
                order["customer"] = customer_response.result

        return order

    async def handle_search_orders(self, query) -> List[Dict[str, Any]]:
        """Search orders across the system."""
        # Search local read model
        # Optionally aggregate with data from other services
        return []


# Production tip: Use dependency injection for the NATS adapter
# so handlers can be tested without real NATS connection
'''

    def generate_utils(self, config: BootstrapConfig) -> str:
        """Generate utilities with SDK usage warnings."""
        return f'''"""Utility functions for {config.project_name}.

⚠️ IMPORTANT: The AegisSDK handles ALL serialization automatically!
- DO NOT implement JSON/msgpack serialization - SDK does this
- DO NOT implement datetime handling for messages - SDK does this
- Use SDK's built-in serialization for all NATS messages

The SDK uses msgpack by default for efficiency. External services
should never need to handle serialization details.
"""

from typing import Any, Dict, List
import hashlib
import uuid
from datetime import datetime

# ⚠️ WARNING: Do not add JSON serialization functions here!
# The SDK handles all message serialization automatically.
# If you need to serialize for non-NATS purposes (like file storage),
# consider using the SDK's serialization utilities instead.


def generate_id(prefix: str = "") -> str:
    """Generate unique ID for entities."""
    unique_id = uuid.uuid4().hex[:8]
    return f"{{prefix}}{{unique_id}}" if prefix else unique_id


def hash_password(password: str) -> str:
    """Hash password using SHA256.

    Note: For production, use proper password hashing like bcrypt.
    """
    return hashlib.sha256(password.encode()).hexdigest()


def slugify(text: str) -> str:
    """Convert text to slug format for URLs or identifiers."""
    return text.lower().replace(" ", "-").replace("_", "-")


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks for batch processing."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{{2,}}$'
    return re.match(pattern, email) is not None


def generate_cache_key(*args) -> str:
    """Generate cache key from arguments."""
    return ":".join(str(arg) for arg in args)


# ⚠️ REMINDER: For any RPC or message passing, the SDK handles serialization!
# You should work with native Python objects and let the SDK convert them.
'''
