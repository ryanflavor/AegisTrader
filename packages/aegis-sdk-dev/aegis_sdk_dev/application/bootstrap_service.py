"""Bootstrap application service."""

from __future__ import annotations

from typing import Any

from aegis_sdk_dev.domain.models import (
    BootstrapConfig,
    ProjectTemplate,
    ServiceConfiguration,
)
from aegis_sdk_dev.ports.console import ConsolePort
from aegis_sdk_dev.ports.environment import EnvironmentPort
from aegis_sdk_dev.ports.nats import NATSConnectionPort


class BootstrapService:
    """Application service for bootstrap use cases."""

    def __init__(
        self,
        console: ConsolePort,
        environment: EnvironmentPort,
        nats: NATSConnectionPort,
    ):
        """Initialize bootstrap service with required ports.

        Args:
            console: Console port for user interaction
            environment: Environment port for detection
            nats: NATS connection port for SDK initialization
        """
        self._console = console
        self._environment = environment
        self._nats = nats

    async def bootstrap_sdk_service(
        self,
        service_name: str,
        nats_url: str,
        kv_bucket: str = "service_registry",
        enable_watchable: bool = True,
    ) -> dict[str, Any]:
        """Bootstrap an SDK service with all necessary components.

        Args:
            service_name: Name of the service
            nats_url: NATS server URL
            kv_bucket: KV bucket name for service registry
            enable_watchable: Enable watchable service discovery

        Returns:
            Service context dictionary with initialized components

        Raises:
            ConnectionError: If unable to connect to NATS
            ValueError: If configuration is invalid
        """
        self._console.print(f"[cyan]Bootstrapping service: {service_name}[/cyan]")

        # Detect environment
        environment = self._environment.detect_environment()
        self._console.print(f"Detected environment: {environment}")

        # Connect to NATS
        self._console.print(f"Connecting to NATS at {nats_url}...")
        try:
            connected = await self._nats.connect(nats_url)
            if not connected:
                raise ConnectionError(f"Failed to connect to NATS at {nats_url}")
            self._console.print_success("Connected to NATS successfully")
        except Exception as e:
            self._console.print_error(f"Failed to connect to NATS: {e}")
            raise

        # Create KV bucket if needed
        self._console.print(f"Checking KV bucket: {kv_bucket}")
        if not await self._nats.bucket_exists(kv_bucket):
            self._console.print(f"Creating KV bucket: {kv_bucket}")
            await self._nats.create_kv_bucket(kv_bucket)

        # Create service context
        context = {
            "service_name": service_name,
            "nats_url": nats_url,
            "kv_bucket": kv_bucket,
            "environment": environment,
            "enable_watchable": enable_watchable,
            "connected": True,
        }

        self._console.print_success(f"Service {service_name} bootstrapped successfully!")

        return context

    def create_bootstrap_config(
        self,
        project_name: str,
        template: str = "basic",
        nats_url: str = "nats://localhost:4222",
        output_dir: str = ".",
        **options: Any,
    ) -> BootstrapConfig:
        """Create a bootstrap configuration for project generation.

        Args:
            project_name: Name of the project
            template: Project template to use
            nats_url: NATS server URL
            output_dir: Output directory for generated files
            **options: Additional options

        Returns:
            BootstrapConfig object
        """
        # Parse template
        try:
            project_template = ProjectTemplate(template)
        except ValueError:
            self._console.print_error(f"Invalid template: {template}")
            self._console.print(
                f"Available templates: {', '.join([t.value for t in ProjectTemplate])}"
            )
            raise

        # Create service configuration
        service_config = ServiceConfiguration(
            service_name=project_name,
            nats_url=nats_url,
            environment=options.get("environment", "auto"),
            kv_bucket=options.get("kv_bucket", "service_registry"),
            enable_watchable=options.get("enable_watchable", True),
            debug=options.get("debug", False),
        )

        # Create bootstrap config
        config = BootstrapConfig(
            project_name=project_name,
            template=project_template,
            service_config=service_config,
            output_dir=output_dir,
            include_tests=options.get("include_tests", True),
            include_docker=options.get("include_docker", True),
            include_k8s=options.get("include_k8s", False),
        )

        return config

    async def cleanup_service(self, service_name: str) -> None:
        """Clean up service resources.

        Args:
            service_name: Name of the service to clean up
        """
        self._console.print(f"Cleaning up service: {service_name}")

        # Disconnect from NATS if connected
        if await self._nats.is_connected():
            await self._nats.disconnect()
            self._console.print("Disconnected from NATS")

        self._console.print_success(f"Service {service_name} cleaned up successfully")
