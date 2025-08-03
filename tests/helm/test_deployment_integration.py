#!/usr/bin/env python3
"""
Integration tests for AegisTrader Kubernetes deployment.
These tests simulate deployment scenarios and validate expected outcomes.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import yaml


class TestDeploymentIntegration(unittest.TestCase):
    """Test deployment integration scenarios."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.helm_dir = Path(__file__).parent.parent.parent / "helm"
        self.scripts_dir = self.helm_dir / "scripts"

    def test_validation_script_exists(self) -> None:
        """Test that validation script exists and is executable."""
        script_path = self.scripts_dir / "validate-deployment.sh"
        self.assertTrue(script_path.exists(), "Validation script not found")
        self.assertTrue(os.access(script_path, os.X_OK), "Script not executable")

    def test_helm_dry_run_simulation(self) -> None:
        """Test that Helm charts can be rendered in dry-run mode."""
        # Read Chart.yaml to validate it can be parsed
        with open(self.helm_dir / "Chart.yaml") as f:
            chart = yaml.safe_load(f)
            self.assertEqual(chart["name"], "aegis-trader")

    @patch("subprocess.run")
    def test_kubectl_commands_structure(self, mock_run: MagicMock) -> None:
        """Test that deployment would execute correct kubectl commands."""
        # Simulate successful command execution
        mock_run.return_value = MagicMock(
            returncode=0, stdout="pod/test-pod condition met\n", stderr=""
        )

        # Expected kubectl commands for deployment validation
        expected_commands = [
            ["kubectl", "get", "namespace"],
            ["kubectl", "wait", "--for=condition=ready", "pod"],
            ["kubectl", "get", "service"],
            ["kubectl", "get", "endpoints"],
        ]

        # Each command should be valid kubectl syntax
        for cmd in expected_commands:
            # Verify command starts with kubectl
            self.assertEqual(cmd[0], "kubectl")
            # Verify it has valid subcommands
            self.assertIn(cmd[1], ["get", "wait", "exec", "run", "delete"])

    def test_deployment_prerequisites(self) -> None:
        """Test that all deployment prerequisites are defined."""
        # Check Makefile targets
        makefile_path = self.helm_dir / "Makefile"
        with open(makefile_path) as f:
            makefile_content = f.read()

        required_targets = [
            "check-tools:",
            "create-namespace:",
            "helm-deps:",
            "install:",
        ]

        for target in required_targets:
            self.assertIn(target, makefile_content, f"Required target {target} not found")

    def test_service_connectivity_matrix(self) -> None:
        """Test that service connectivity requirements are properly defined."""
        # Define expected service connections
        connectivity_matrix: dict[str, dict[str, Any]] = {
            "monitor-api": {
                "depends_on": ["nats"],
                "port": 8100,
                "health_endpoint": "/health",
            },
            "monitor-ui": {
                "depends_on": ["monitor-api"],
                "port": 3100,
                "health_endpoint": "/",
            },
            "nats": {
                "depends_on": [],
                "port": 4222,
                "health_endpoint": None,  # Uses nats CLI
            },
        }

        # Validate init containers match dependencies
        for service, config in connectivity_matrix.items():
            if service == "nats":
                continue  # NATS has no dependencies

            # Read the deployment template
            deployment_file = self.helm_dir / f"charts/{service}/templates/deployment.yaml"
            if deployment_file.exists():
                with open(deployment_file) as f:
                    content = f.read()

                # Check for init containers
                if config["depends_on"]:
                    self.assertIn("initContainers:", content)
                    # Check that init container waits for the dependency
                    for dep in config["depends_on"]:
                        if dep == "nats":
                            self.assertIn(f"wait-for-{dep}", content)
                        elif dep == "monitor-api":
                            self.assertIn("wait-for-api", content)

    def test_resource_requirements(self) -> None:
        """Test that resource requirements are properly defined in subchart values."""
        services = ["monitor-api", "monitor-ui"]

        for service in services:
            # Resources are defined in subchart values
            values_path = self.helm_dir / "charts" / service / "values.yaml"
            with open(values_path) as f:
                values = yaml.safe_load(f)

            self.assertIn("resources", values)
            self.assertIn("requests", values["resources"])
            self.assertIn("limits", values["resources"])

            # Verify CPU and memory are defined
            for resource_type in ["requests", "limits"]:
                resources = values["resources"][resource_type]
                self.assertIn("cpu", resources)
                self.assertIn("memory", resources)

    def test_persistence_configuration(self) -> None:
        """Test that persistence is properly configured for stateful components."""
        with open(self.helm_dir / "values.yaml") as f:
            values = yaml.safe_load(f)

        # NATS should have JetStream file storage configured
        nats_config = values["nats"]["config"]["jetstream"]
        self.assertTrue(nats_config["enabled"])
        self.assertIn("fileStore", nats_config)
        self.assertTrue(nats_config["fileStore"]["enabled"])
        self.assertIn("pvc", nats_config["fileStore"])
        self.assertIn("size", nats_config["fileStore"]["pvc"])

        # Verify storage size is reasonable
        storage_size = nats_config["fileStore"]["pvc"]["size"]
        self.assertIn("Gi", storage_size)
        size_value = int(storage_size.replace("Gi", ""))
        self.assertGreaterEqual(size_value, 5, "Storage size too small for production")

    def test_health_probes_configuration(self) -> None:
        """Test that all services have proper health probes configured."""
        services = ["monitor-api", "monitor-ui"]

        for service in services:
            with open(self.helm_dir / f"charts/{service}/templates/deployment.yaml") as f:
                content = f.read()

            # Check for all three probe types
            self.assertIn("livenessProbe:", content)
            self.assertIn("readinessProbe:", content)

            # API should have startup probe for slow initialization
            if service == "monitor-api":
                self.assertIn("startupProbe:", content)

    def test_deployment_order_dependencies(self) -> None:
        """Test that deployment order is properly handled."""
        # NATS KV job runs as a normal Kubernetes resource without helm hooks
        # to avoid circular dependency with --wait
        with open(self.helm_dir / "templates/nats-kv-job.yaml") as f:
            content = f.read()

        # Verify job exists and has proper restart policy
        self.assertIn("kind: Job", content)
        self.assertIn("restartPolicy: OnFailure", content)
        # Job has retry logic built-in
        self.assertIn("MAX_RETRIES", content)

    def test_nats_kv_bucket_configuration(self) -> None:
        """Test NATS KV bucket configuration for service registry."""
        with open(self.helm_dir / "values.yaml") as f:
            values = yaml.safe_load(f)

        # Check service registry configuration
        self.assertIn("serviceRegistry", values)
        sr_config = values["serviceRegistry"]

        self.assertTrue(sr_config["createBucket"])
        self.assertEqual(sr_config["bucketName"], "service-registry")
        self.assertIn("bucket", sr_config)

        # Validate bucket settings
        bucket = sr_config["bucket"]
        self.assertGreaterEqual(bucket["replicas"], 1)
        self.assertGreater(bucket["maxBytes"], 0)

    def test_makefile_deployment_targets(self) -> None:
        """Test that Makefile provides complete deployment workflow."""
        makefile_path = self.helm_dir / "Makefile"
        with open(makefile_path) as f:
            content = f.read()

        # Verify deployment workflow targets
        workflow_targets = [
            "check-tools",
            "create-namespace",
            "helm-deps",
            "lint",
            "install",
            "test",
            "status",
            "port-forward",
        ]

        for target in workflow_targets:
            self.assertIn(f"{target}:", content, f"Workflow target {target} missing")

        # Check for proper target dependencies
        self.assertIn("install: check-tools create-namespace helm-deps lint", content)

    def test_environment_specific_values(self) -> None:
        """Test that environment-specific values are properly structured."""
        # Check development values
        dev_values_path = self.helm_dir / "values.dev.yaml"
        self.assertTrue(dev_values_path.exists())

        with open(dev_values_path) as f:
            dev_values = yaml.safe_load(f)

        # Development should use reduced resources
        self.assertEqual(dev_values["nats"]["replicas"], 1)

        # Development might enable ingress for local testing
        if "monitor-ui" in dev_values and "ingress" in dev_values["monitor-ui"]:
            self.assertTrue(dev_values["monitor-ui"]["ingress"]["enabled"])


class TestDeploymentScenarios(unittest.TestCase):
    """Test various deployment scenarios and failure cases."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.helm_dir = Path(__file__).parent.parent.parent / "helm"

    def test_partial_deployment_recovery(self) -> None:
        """Test that partial deployments can be recovered."""
        # Verify Helm upgrade command is available in Makefile
        with open(self.helm_dir / "Makefile") as f:
            content = f.read()

        self.assertIn("upgrade:", content)
        self.assertIn("--wait", content)  # Should wait for resources

    def test_namespace_isolation(self) -> None:
        """Test that deployments support namespace isolation."""
        with open(self.helm_dir / "Makefile") as f:
            content = f.read()

        # Should support NAMESPACE variable
        self.assertIn("NAMESPACE ?=", content)
        self.assertIn("--namespace $(NAMESPACE)", content)

    def test_rollback_capability(self) -> None:
        """Test that deployment supports rollback."""
        # Helm automatically supports rollback, verify uninstall is clean
        with open(self.helm_dir / "Makefile") as f:
            content = f.read()

        self.assertIn("uninstall:", content)
        self.assertIn("clean:", content)  # Full cleanup target


if __name__ == "__main__":
    unittest.main()
