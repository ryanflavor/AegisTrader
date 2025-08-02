#!/usr/bin/env python3
"""
Contract tests for Helm charts following hexagonal architecture principles.
Tests enforce boundaries between domain (chart configuration), application
(chart rendering), and infrastructure (Kubernetes resources).
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


# Domain Layer - Chart configuration models with Pydantic v2 strict validation
class ChartMetadata(BaseModel):
    """Domain model for Helm chart metadata."""

    model_config = ConfigDict(strict=True)

    api_version: str = Field(alias="apiVersion", pattern="^v2$")
    name: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    app_version: str = Field(alias="appVersion")
    description: str = Field(min_length=1)
    type: str = Field(pattern="^(application|library)$")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate chart name follows conventions."""
        if not v.replace("-", "").isalnum():
            raise ValueError("Chart name must be alphanumeric with hyphens")
        return v


class ServiceConfiguration(BaseModel):
    """Domain model for service configuration."""

    model_config = ConfigDict(strict=True)

    type: str = Field(pattern="^(ClusterIP|LoadBalancer|NodePort)$")
    port: int = Field(gt=0, le=65535)


class ResourceRequirements(BaseModel):
    """Domain model for resource requirements."""

    model_config = ConfigDict(strict=True)

    cpu: str = Field(pattern=r"^\d+m?$")
    memory: str = Field(pattern=r"^\d+[MG]i$")


class Resources(BaseModel):
    """Domain model for resource specifications."""

    model_config = ConfigDict(strict=True)

    requests: ResourceRequirements
    limits: ResourceRequirements


class ProbeConfiguration(BaseModel):
    """Domain model for probe configuration."""

    model_config = ConfigDict(strict=True)

    enabled: bool
    initial_delay_seconds: int = Field(alias="initialDelaySeconds", ge=0)
    period_seconds: int = Field(alias="periodSeconds", gt=0)
    failure_threshold: int | None = Field(alias="failureThreshold", ge=1, default=None)


# Port Layer - Interfaces for chart operations
class ChartRenderer(Protocol):
    """Port interface for chart rendering operations."""

    def render(
        self, release_name: str, namespace: str, values: dict[str, Any] | None = None
    ) -> str:
        """Render Helm templates with given configuration."""
        ...


class ChartValidator(Protocol):
    """Port interface for chart validation operations."""

    def validate_structure(self, chart_path: Path) -> bool:
        """Validate chart structure and dependencies."""
        ...

    def validate_values(self, values: dict[str, Any]) -> bool:
        """Validate values against schema."""
        ...


# Application Layer - Chart validation service
class HelmChartValidationService:
    """Application service for validating Helm charts."""

    def __init__(self, renderer: ChartRenderer, validator: ChartValidator) -> None:
        """Initialize with required adapters."""
        self.renderer = renderer
        self.validator = validator

    def validate_chart_metadata(self, chart_path: Path) -> ChartMetadata:
        """Validate and return chart metadata."""
        chart_yaml = chart_path / "Chart.yaml"
        if not chart_yaml.exists():
            raise FileNotFoundError(f"Chart.yaml not found at {chart_path}")

        with open(chart_yaml) as f:
            data = yaml.safe_load(f)

        return ChartMetadata(**data)

    def validate_service_configuration(
        self, values: dict[str, Any], service_name: str
    ) -> ServiceConfiguration:
        """Validate service configuration from values."""
        service_config = values.get(service_name, {}).get("service", {})
        if not service_config:
            raise ValueError(f"Service configuration not found for {service_name}")

        return ServiceConfiguration(**service_config)

    def validate_resource_limits(self, values: dict[str, Any], service_name: str) -> Resources:
        """Validate resource limits configuration."""
        resources = values.get(service_name, {}).get("resources", {})
        if not resources:
            raise ValueError(f"Resource configuration not found for {service_name}")

        return Resources(**resources)


# Infrastructure Layer - Helm CLI adapter
class HelmCliAdapter:
    """Infrastructure adapter for Helm CLI operations."""

    def __init__(self, chart_path: Path) -> None:
        """Initialize with chart path."""
        self.chart_path = chart_path

    def render(
        self, release_name: str, namespace: str, values: dict[str, Any] | None = None
    ) -> str:
        """Render Helm templates using CLI."""
        cmd = [
            "helm",
            "template",
            release_name,
            str(self.chart_path),
            "--namespace",
            namespace,
        ]

        if values:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                yaml.dump(values, f)
                temp_values = f.name
            cmd.extend(["-f", temp_values])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Helm template failed: {e.stderr}") from e

    def validate_structure(self, chart_path: Path) -> bool:
        """Validate chart structure using helm lint."""
        cmd = ["helm", "lint", str(chart_path)]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    def validate_values(self, values: dict[str, Any]) -> bool:
        """Basic values validation."""
        required_keys = ["nats", "monitor-api", "monitor-ui"]
        return all(key in values for key in required_keys)


# Test Suite
@unittest.skipIf(not Path("helm").exists(), "Helm directory not found")
class TestHelmChartContracts(unittest.TestCase):
    """Contract tests for Helm charts using hexagonal architecture."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.helm_dir = Path(__file__).parent.parent.parent / "helm"
        self.renderer = HelmCliAdapter(self.helm_dir)
        self.validator = HelmCliAdapter(self.helm_dir)
        self.service = HelmChartValidationService(self.renderer, self.validator)

    def test_main_chart_metadata_contract(self) -> None:
        """Test main chart metadata follows domain contract."""
        metadata = self.service.validate_chart_metadata(self.helm_dir)
        self.assertEqual(metadata.api_version, "v2")
        self.assertEqual(metadata.name, "aegis-trader")
        self.assertIsInstance(metadata.version, str)
        self.assertEqual(metadata.type, "application")

    def test_subchart_metadata_contracts(self) -> None:
        """Test subchart metadata follows domain contracts."""
        subcharts = ["monitor-api", "monitor-ui"]

        for subchart in subcharts:
            with self.subTest(subchart=subchart):
                subchart_path = self.helm_dir / "charts" / subchart
                metadata = self.service.validate_chart_metadata(subchart_path)
                self.assertEqual(metadata.name, subchart)
                self.assertEqual(metadata.type, "application")

    def test_service_configuration_contracts(self) -> None:
        """Test service configurations follow domain contracts."""
        # Load subchart values
        services = [
            ("monitor-api", self.helm_dir / "charts" / "monitor-api" / "values.yaml"),
            ("monitor-ui", self.helm_dir / "charts" / "monitor-ui" / "values.yaml"),
        ]

        for service_name, values_path in services:
            with self.subTest(service=service_name):
                with open(values_path) as f:
                    values = yaml.safe_load(f)

                service_config = self.service.validate_service_configuration(
                    {service_name: values}, service_name
                )
                self.assertEqual(service_config.type, "ClusterIP")
                self.assertGreater(service_config.port, 0)

    def test_resource_requirements_contracts(self) -> None:
        """Test resource requirements follow domain contracts."""
        services = [
            (
                "monitor-api",
                self.helm_dir / "charts" / "monitor-api" / "values.yaml",
                "1000m",
                "2Gi",
            ),
            (
                "monitor-ui",
                self.helm_dir / "charts" / "monitor-ui" / "values.yaml",
                "500m",
                "1Gi",
            ),
        ]

        for service_name, values_path, expected_cpu, expected_memory in services:
            with self.subTest(service=service_name):
                with open(values_path) as f:
                    values = yaml.safe_load(f)

                resources = self.service.validate_resource_limits(
                    {service_name: values}, service_name
                )
                self.assertEqual(resources.requests.cpu, expected_cpu)
                self.assertEqual(resources.requests.memory, expected_memory)

    def test_deployment_renders_with_valid_structure(self) -> None:
        """Test deployments render with valid Kubernetes structure."""
        output = self.renderer.render("test-release", "test-namespace")
        docs = list(yaml.safe_load_all(output))

        # Validate deployment structure
        deployments = [d for d in docs if d and d.get("kind") == "Deployment"]
        self.assertGreater(len(deployments), 0)

        for deployment in deployments:
            with self.subTest(deployment=deployment.get("metadata", {}).get("name")):
                # Validate required fields
                self.assertIn("apiVersion", deployment)
                self.assertIn("metadata", deployment)
                self.assertIn("spec", deployment)

                # Validate spec structure
                spec = deployment["spec"]
                self.assertIn("replicas", spec)
                self.assertIn("selector", spec)
                self.assertIn("template", spec)

                # Validate pod template
                template = spec["template"]
                self.assertIn("metadata", template)
                self.assertIn("spec", template)

                # Validate containers
                containers = template["spec"]["containers"]
                self.assertIsInstance(containers, list)
                self.assertGreater(len(containers), 0)

    def test_service_renders_with_valid_structure(self) -> None:
        """Test services render with valid Kubernetes structure."""
        output = self.renderer.render("test-release", "test-namespace")
        docs = list(yaml.safe_load_all(output))

        services = [d for d in docs if d and d.get("kind") == "Service"]
        self.assertGreater(len(services), 0)

        for service in services:
            with self.subTest(service=service.get("metadata", {}).get("name")):
                # Validate required fields
                self.assertIn("apiVersion", service)
                self.assertIn("metadata", service)
                self.assertIn("spec", service)

                # Validate spec structure
                spec = service["spec"]
                # Type is optional (defaults to ClusterIP)
                # Headless services use clusterIP: None
                if "type" in spec:
                    self.assertIn(
                        spec["type"],
                        ["ClusterIP", "LoadBalancer", "NodePort", "ExternalName"],
                    )
                self.assertIn("ports", spec)
                self.assertIn("selector", spec)

    def test_chart_dependencies_resolved(self) -> None:
        """Test all chart dependencies are properly resolved."""
        # Check Chart.lock exists
        chart_lock = self.helm_dir / "Chart.lock"
        self.assertTrue(chart_lock.exists(), "Chart.lock not found - dependencies not resolved")

        # Validate dependency resolution
        with open(chart_lock) as f:
            lock_data = yaml.safe_load(f)

        self.assertIn("dependencies", lock_data)
        dependencies = lock_data["dependencies"]

        # Check all dependencies are resolved
        expected_deps = ["nats", "monitor-api", "monitor-ui"]
        resolved_deps = [dep["name"] for dep in dependencies]

        for expected in expected_deps:
            self.assertIn(expected, resolved_deps, f"Dependency {expected} not resolved")

    def test_values_override_inheritance(self) -> None:
        """Test values properly override from parent to subcharts."""
        # Test with custom image tag
        custom_values = {
            "global": {"imageTag": "v1.2.3"},
            "monitor-api": {"image": {"tag": "v1.2.3"}},
            "monitor-ui": {"image": {"tag": "v1.2.3"}},
        }

        output = self.renderer.render("test-release", "test-namespace", custom_values)
        docs = list(yaml.safe_load_all(output))

        # Check deployments use custom tag
        deployments = [d for d in docs if d and d.get("kind") == "Deployment"]
        for deployment in deployments:
            if "monitor-" in deployment["metadata"]["name"]:
                containers = deployment["spec"]["template"]["spec"]["containers"]
                for container in containers:
                    self.assertIn("v1.2.3", container["image"])


if __name__ == "__main__":
    unittest.main()
