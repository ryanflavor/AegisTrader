"""Configuration helpers for AegisSDK developer experience."""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from aegis_sdk.application.dependency_provider import DependencyProvider
from aegis_sdk.application.service import Service, ServiceConfig
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.developer.bootstrap import bootstrap_sdk
from aegis_sdk.developer.environment import Environment, detect_environment
from aegis_sdk.developer.k8s_discovery import get_nats_url_with_retry
from aegis_sdk.domain.value_objects import FailoverPolicy

logger = logging.getLogger(__name__)


class SDKConfig(BaseModel):
    """Simplified SDK configuration for developers."""

    service_name: str = Field(..., description="Your service name")
    nats_url: str = Field(default="auto", description="NATS URL or 'auto' for K8s discovery")
    environment: Environment = Field(default=Environment.LOCAL_K8S)
    debug: bool = Field(default=True, description="Enable debug logging")
    version: str = Field(default="1.0.0", description="Service version")
    namespace: str = Field(default="aegis-trader", description="K8s namespace")


class K8sNATSConfig(BaseModel):
    """K8s-specific NATS configuration."""

    namespace: str = Field(default="aegis-trader")
    service_name: str = Field(default="aegis-trader-nats")
    port: int = Field(default=4222)
    use_port_forward: bool = Field(default=True)


async def discover_k8s_config() -> K8sNATSConfig:
    """Automatically discover K8s NATS configuration.

    Returns:
        K8sNATSConfig with discovered settings
    """
    config = K8sNATSConfig()

    # Try to get NATS URL with retry
    nats_url = await get_nats_url_with_retry(
        namespace=config.namespace,
        service_name=config.service_name,
        use_port_forward=config.use_port_forward,
    )

    # Update port if different from default
    if "localhost" in nats_url:
        config.use_port_forward = True

    return config


async def quick_setup(
    service_name: str,
    service_type: Literal["service", "single-active"] = "service",
    **kwargs: Any,
) -> Service | SingleActiveService:
    """Quick setup helper for creating services with auto-configuration.

    Args:
        service_name: Name of your service
        service_type: Type of service to create
        **kwargs: Additional configuration options

    Returns:
        Configured service instance ready to use

    Example:
        >>> service = await quick_setup("my-service")
        >>> @service.rpc("echo")
        >>> async def echo(params):
        >>>     return {"echo": params}
        >>> await service.start()
    """
    # Detect environment
    env = detect_environment()

    # Build configuration
    config = SDKConfig(
        service_name=service_name,
        environment=env,
        **kwargs,
    )

    # Get NATS URL if auto
    if config.nats_url == "auto":
        if env == Environment.LOCAL_K8S:
            k8s_config = await discover_k8s_config()
            nats_url = await get_nats_url_with_retry(
                namespace=k8s_config.namespace,
                service_name=k8s_config.service_name,
                use_port_forward=k8s_config.use_port_forward,
            )
        elif env == Environment.DOCKER:
            nats_url = "nats://host.docker.internal:4222"
        elif env == Environment.PRODUCTION:
            nats_url = "nats://aegis-trader-nats:4222"
        else:
            nats_url = "nats://localhost:4222"
    else:
        nats_url = config.nats_url

    # Configure logging if debug
    if config.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    # Create service configuration
    ServiceConfig(
        service_name=config.service_name,
        version=config.version,
    )

    # Bootstrap SDK
    components = await bootstrap_sdk(nats_url, config.service_name)

    # Create service based on type
    if service_type == "single-active":
        from aegis_sdk.application.single_active_dtos import SingleActiveConfig

        failover_policy = kwargs.get("failover_policy", FailoverPolicy.balanced())
        single_config = SingleActiveConfig(
            service_name=config.service_name,
            version=config.version,
            failover_policy=failover_policy,
        )
        service = SingleActiveService(
            config=single_config,
            message_bus=components["message_bus"],
            service_registry=components["service_registry"],
            service_discovery=components["service_discovery"],
            logger=components["logger"],
        )
    else:
        service = Service(
            service_name=config.service_name,
            message_bus=components["message_bus"],
            version=config.version,
            service_registry=components["service_registry"],
            service_discovery=components["service_discovery"],
            logger=components["logger"],
        )

    logger.info(
        f"Service '{service_name}' configured for {env.value} environment (NATS: {nats_url})"
    )

    return service


async def create_service(
    name: str,
    service_type: Literal["service", "single-active"] = "service",
    **kwargs: Any,
) -> Service | SingleActiveService:
    """Create a service with automatic K8s configuration.

    Args:
        name: Service name
        service_type: Type of service to create
        **kwargs: Additional configuration options

    Returns:
        Configured service instance
    """
    return await quick_setup(name, service_type, **kwargs)


async def create_external_client(namespace: str = "aegis-trader") -> DependencyProvider:
    """Create an external client (like monitor-api) for management tasks.

    Args:
        namespace: K8s namespace

    Returns:
        DependencyProvider configured for external client use

    Example:
        >>> provider = await create_external_client()
        >>> registry = provider.service_registry()
        >>> services = await registry.list_services()
    """
    # Get NATS URL
    k8s_config = await discover_k8s_config()
    nats_url = await get_nats_url_with_retry(
        namespace=k8s_config.namespace,
        service_name=k8s_config.service_name,
        use_port_forward=k8s_config.use_port_forward,
    )

    # Bootstrap and return provider
    provider = await bootstrap_sdk(nats_url, "external-client")

    logger.info(f"External client configured for {namespace} namespace (NATS: {nats_url})")

    return provider
