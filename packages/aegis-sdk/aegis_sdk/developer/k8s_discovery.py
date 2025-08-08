"""Kubernetes service discovery utilities for AegisSDK."""

from __future__ import annotations

import asyncio
import json
import subprocess

from pydantic import BaseModel, Field


class K8sService(BaseModel):
    """Kubernetes service information."""

    name: str = Field(..., description="Service name")
    namespace: str = Field(..., description="Service namespace")
    cluster_ip: str = Field(..., description="Cluster IP address")
    port: int = Field(..., description="Service port")

    @property
    def cluster_url(self) -> str:
        """Get in-cluster URL for this service."""
        return f"{self.name}.{self.namespace}.svc.cluster.local:{self.port}"

    @property
    def nats_url(self) -> str:
        """Get NATS connection URL."""
        return f"nats://{self.cluster_ip}:{self.port}"


async def discover_nats_service(
    namespace: str = "aegis-trader",
    service_name: str = "aegis-trader-nats",
    port_name: str = "nats",
) -> K8sService | None:
    """Discover NATS service from Kubernetes.

    Args:
        namespace: Kubernetes namespace
        service_name: Name of the NATS service
        port_name: Name of the port (optional)

    Returns:
        K8sService if found, None otherwise
    """
    try:
        # Get service info using kubectl
        cmd = ["kubectl", "get", "service", service_name, "-n", namespace, "-o", "json"]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            return None

        service_data = json.loads(stdout.decode())

        # Extract service information
        spec = service_data.get("spec", {})
        cluster_ip = spec.get("clusterIP")

        # Find the port
        port = None
        for port_spec in spec.get("ports", []):
            if (port_name and port_spec.get("name") == port_name) or not port_name:
                port = port_spec.get("port")
                break

        if cluster_ip and port:
            return K8sService(
                name=service_name,
                namespace=namespace,
                cluster_ip=cluster_ip,
                port=port,
            )
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError):
        pass

    return None


async def check_port_forward(host: str = "localhost", port: int = 4222) -> bool:
    """Check if port forwarding is active.

    Args:
        host: Host to check
        port: Port to check

    Returns:
        True if port is accessible
    """
    try:
        # Try to connect to the port
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.0)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def setup_port_forward(
    namespace: str = "aegis-trader",
    service_name: str = "aegis-trader-nats",
    local_port: int = 4222,
    remote_port: int = 4222,
) -> asyncio.subprocess.Process | None:
    """Setup kubectl port-forward to NATS service.

    Args:
        namespace: Kubernetes namespace
        service_name: Name of the service
        local_port: Local port to forward to
        remote_port: Remote port to forward from

    Returns:
        Subprocess handle if successful
    """
    # Check if port forward is already active
    if await check_port_forward("localhost", local_port):
        return None  # Already forwarded

    cmd = [
        "kubectl",
        "port-forward",
        "-n",
        namespace,
        f"svc/{service_name}",
        f"{local_port}:{remote_port}",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Give port-forward time to establish
        await asyncio.sleep(1)

        # Check if it's working
        if await check_port_forward("localhost", local_port):
            return process
        else:
            process.terminate()
            await process.wait()
    except subprocess.SubprocessError:
        pass

    return None


async def get_nats_url_with_retry(
    namespace: str = "aegis-trader",
    service_name: str = "aegis-trader-nats",
    use_port_forward: bool = True,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> str:
    """Get NATS URL with automatic port forwarding and retry.

    Args:
        namespace: Kubernetes namespace
        service_name: Name of the NATS service
        use_port_forward: Whether to use port forwarding
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        NATS connection URL
    """
    import logging

    logger = logging.getLogger(__name__)

    # Check if we're in a K8s pod (in-cluster)
    import os

    in_cluster = os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount")

    if in_cluster:
        # We're running inside K8s, use cluster DNS
        cluster_url = f"nats://{service_name}.{namespace}.svc.cluster.local:4222"
        logger.info(f"Running in K8s cluster, using cluster URL: {cluster_url}")
        return cluster_url

    # We're outside K8s, try port forwarding first if enabled
    if use_port_forward:
        logger.info("Running outside K8s, checking for port-forward to NATS...")

        for attempt in range(max_retries):
            # Check if port forward is already active
            if await check_port_forward():
                logger.info("✓ Port-forward to NATS is active on localhost:4222")
                return "nats://localhost:4222"

            logger.warning(
                f"Port-forward not detected (attempt {attempt + 1}/{max_retries}). "
                f"Please run: kubectl port-forward -n {namespace} svc/{service_name} 4222:4222"
            )

            # Try to setup port forward automatically
            logger.info("Attempting to establish port-forward automatically...")
            process = await setup_port_forward(
                namespace=namespace,
                service_name=service_name,
            )

            if process or await check_port_forward():
                logger.info("✓ Successfully established port-forward to NATS")
                return "nats://localhost:4222"

            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)

        logger.error(
            f"Failed to establish port-forward after {max_retries} attempts. "
            f"Please manually run: kubectl port-forward -n {namespace} svc/{service_name} 4222:4222"
        )

    # Try service discovery as fallback
    logger.info("Attempting service discovery...")
    service = await discover_nats_service(namespace, service_name)
    if service:
        logger.info(f"Found NATS service via discovery: {service.nats_url}")
        return service.nats_url

    # Default fallback to localhost
    logger.warning(
        "Could not detect NATS connection method, defaulting to localhost:4222. "
        "If this fails, please ensure NATS is accessible."
    )
    return "nats://localhost:4222"
