#!/usr/bin/env python3
"""
Test suite for AegisTrader Helm charts following TDD standards.
Tests chart structure, templating, and configuration validation.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

# Check if helm is available
try:
    subprocess.run(["helm", "version"], capture_output=True, check=True)
    HELM_AVAILABLE = True
except (subprocess.CalledProcessError, FileNotFoundError):
    HELM_AVAILABLE = False


class TestHelmChartStructure(unittest.TestCase):
    """Test Helm chart structure and files existence."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.helm_dir = Path(__file__).parent.parent.parent / "helm"
        self.chart_yaml = self.helm_dir / "Chart.yaml"
        self.values_yaml = self.helm_dir / "values.yaml"

    def test_main_chart_exists(self) -> None:
        """Test that main Chart.yaml exists and is valid."""
        self.assertTrue(self.chart_yaml.exists(), "Chart.yaml not found")

        with open(self.chart_yaml) as f:
            chart = yaml.safe_load(f)

        self.assertEqual(chart["apiVersion"], "v2")
        self.assertEqual(chart["name"], "aegis-trader")
        self.assertIn("version", chart)
        self.assertIn("dependencies", chart)

    def test_values_file_exists(self) -> None:
        """Test that values.yaml exists with required configuration."""
        self.assertTrue(self.values_yaml.exists(), "values.yaml not found")

        with open(self.values_yaml) as f:
            values = yaml.safe_load(f)

        # Test required top-level keys
        self.assertIn("nats", values)
        self.assertIn("monitor-api", values)
        self.assertIn("monitor-ui", values)
        self.assertIn("serviceRegistry", values)

    def test_subchart_structure(self) -> None:
        """Test that subcharts have proper structure."""
        subcharts = ["monitor-api", "monitor-ui"]

        for subchart in subcharts:
            subchart_dir = self.helm_dir / "charts" / subchart
            self.assertTrue(subchart_dir.exists(), f"{subchart} directory not found")

            # Check required files
            chart_yaml = subchart_dir / "Chart.yaml"
            values_yaml = subchart_dir / "values.yaml"
            templates_dir = subchart_dir / "templates"

            self.assertTrue(chart_yaml.exists(), f"{subchart}/Chart.yaml not found")
            self.assertTrue(values_yaml.exists(), f"{subchart}/values.yaml not found")
            self.assertTrue(templates_dir.exists(), f"{subchart}/templates not found")

            # Verify Chart.yaml content
            with open(chart_yaml) as f:
                chart = yaml.safe_load(f)
                self.assertEqual(chart["name"], subchart)
                self.assertEqual(chart["version"], "1.0.1")


@unittest.skipIf(not HELM_AVAILABLE, "Helm CLI not available")
class TestHelmTemplateRendering(unittest.TestCase):
    """Test Helm template rendering with various configurations."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.helm_dir = Path(__file__).parent.parent.parent / "helm"
        self.test_release = "test-release"
        self.test_namespace = "test-namespace"

    def _render_templates(self, values_override: dict[str, Any] | None = None) -> str:
        """Render Helm templates with optional value overrides."""
        cmd = [
            "helm",
            "template",
            self.test_release,
            str(self.helm_dir),
            "--namespace",
            self.test_namespace,
        ]

        if values_override:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump(values_override, f)
                temp_values = f.name
            cmd.extend(["-f", temp_values])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            self.fail(f"Helm template failed: {e.stderr}")
        finally:
            if values_override and "temp_values" in locals():
                os.unlink(temp_values)

    def test_template_renders_without_errors(self) -> None:
        """Test that templates render without errors using default values."""
        output = self._render_templates()
        self.assertIn("kind:", output)
        self.assertIn("apiVersion:", output)

    def test_nats_deployment_configuration(self) -> None:
        """Test NATS deployment configuration is properly rendered."""
        output = self._render_templates()

        # Parse YAML documents
        docs = list(yaml.safe_load_all(output))

        # Find NATS-related resources
        nats_resources = [
            d for d in docs if d and "nats" in d.get("metadata", {}).get("name", "")
        ]
        self.assertGreater(len(nats_resources), 0, "No NATS resources found")

    def test_monitor_api_deployment(self) -> None:
        """Test monitor-api deployment is properly configured."""
        output = self._render_templates()
        docs = list(yaml.safe_load_all(output))

        # Find monitor-api deployment
        api_deployments = [
            d
            for d in docs
            if d
            and d.get("kind") == "Deployment"
            and "monitor-api" in d.get("metadata", {}).get("name", "")
        ]
        self.assertEqual(len(api_deployments), 1, "monitor-api deployment not found")

        deployment = api_deployments[0]
        containers = deployment["spec"]["template"]["spec"]["containers"]
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0]["image"], "aegistrader-monitor-api:latest")

        # Check init containers
        init_containers = deployment["spec"]["template"]["spec"].get(
            "initContainers", []
        )
        self.assertEqual(len(init_containers), 1)
        self.assertEqual(init_containers[0]["name"], "wait-for-nats")

    def test_monitor_ui_deployment(self) -> None:
        """Test monitor-ui deployment is properly configured."""
        output = self._render_templates()
        docs = list(yaml.safe_load_all(output))

        # Find monitor-ui deployment
        ui_deployments = [
            d
            for d in docs
            if d
            and d.get("kind") == "Deployment"
            and "monitor-ui" in d.get("metadata", {}).get("name", "")
        ]
        self.assertEqual(len(ui_deployments), 1, "monitor-ui deployment not found")

        deployment = ui_deployments[0]
        containers = deployment["spec"]["template"]["spec"]["containers"]
        self.assertEqual(len(containers), 1)
        self.assertEqual(containers[0]["image"], "aegistrader-monitor-ui:latest")

    def test_services_are_created(self) -> None:
        """Test that all required services are created."""
        output = self._render_templates()
        docs = list(yaml.safe_load_all(output))

        services = [d for d in docs if d and d.get("kind") == "Service"]
        service_names = [s["metadata"]["name"] for s in services]

        # Check required services exist
        self.assertIn(f"{self.test_release}-monitor-api", service_names)
        self.assertIn(f"{self.test_release}-monitor-ui", service_names)

    def test_nats_kv_job_configuration(self) -> None:
        """Test NATS KV bucket creation job is properly configured."""
        output = self._render_templates()
        docs = list(yaml.safe_load_all(output))

        # Find KV creation job
        kv_jobs = [
            d
            for d in docs
            if d
            and d.get("kind") == "Job"
            and "create-kv-bucket" in d.get("metadata", {}).get("name", "")
        ]
        self.assertEqual(len(kv_jobs), 1, "NATS KV creation job not found")

        job = kv_jobs[0]
        # The job runs as a normal Kubernetes resource without helm hooks
        # to avoid circular dependency with --wait
        self.assertEqual(job["kind"], "Job")
        self.assertEqual(job["spec"]["template"]["spec"]["restartPolicy"], "OnFailure")


class TestHelmValueOverrides(unittest.TestCase):
    """Test Helm chart behavior with different value overrides."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.helm_dir = Path(__file__).parent.parent.parent / "helm"

    def test_development_values_override(self) -> None:
        """Test that development values properly override defaults."""
        dev_values_file = self.helm_dir / "values.dev.yaml"
        self.assertTrue(dev_values_file.exists(), "values.dev.yaml not found")

        with open(dev_values_file) as f:
            dev_values = yaml.safe_load(f)

        # Test development-specific settings
        self.assertEqual(dev_values["nats"]["replicas"], 1)
        self.assertEqual(dev_values["monitor-ui"]["ingress"]["enabled"], True)

    def test_resource_limits_configuration(self) -> None:
        """Test that resource limits are properly configured in subchart values."""
        # Check monitor-api resources
        api_values_file = self.helm_dir / "charts" / "monitor-api" / "values.yaml"
        with open(api_values_file) as f:
            api_values = yaml.safe_load(f)

        api_resources = api_values["resources"]
        self.assertEqual(api_resources["requests"]["cpu"], "1000m")
        self.assertEqual(api_resources["requests"]["memory"], "2Gi")
        self.assertEqual(api_resources["limits"]["cpu"], "1000m")
        self.assertEqual(api_resources["limits"]["memory"], "2Gi")

        # Check monitor-ui resources
        ui_values_file = self.helm_dir / "charts" / "monitor-ui" / "values.yaml"
        with open(ui_values_file) as f:
            ui_values = yaml.safe_load(f)

        ui_resources = ui_values["resources"]
        self.assertEqual(ui_resources["requests"]["cpu"], "500m")
        self.assertEqual(ui_resources["requests"]["memory"], "1Gi")

    def test_probe_configuration(self) -> None:
        """Test that health probes are properly configured in subchart values."""
        # Check monitor-api probes
        api_values_file = self.helm_dir / "charts" / "monitor-api" / "values.yaml"
        with open(api_values_file) as f:
            api_values = yaml.safe_load(f)

        api_probes = api_values["probes"]
        self.assertTrue(api_probes["liveness"]["enabled"])
        self.assertTrue(api_probes["readiness"]["enabled"])
        self.assertTrue(api_probes["startup"]["enabled"])
        self.assertEqual(api_probes["startup"]["failureThreshold"], 60)

        # Check monitor-ui probes
        ui_values_file = self.helm_dir / "charts" / "monitor-ui" / "values.yaml"
        with open(ui_values_file) as f:
            ui_values = yaml.safe_load(f)

        ui_probes = ui_values["probes"]
        self.assertTrue(ui_probes["liveness"]["enabled"])
        self.assertTrue(ui_probes["readiness"]["enabled"])


class TestHelmChartDependencies(unittest.TestCase):
    """Test Helm chart dependencies and version constraints."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.helm_dir = Path(__file__).parent.parent.parent / "helm"

    def test_nats_dependency_configuration(self) -> None:
        """Test NATS dependency is properly configured."""
        with open(self.helm_dir / "Chart.yaml") as f:
            chart = yaml.safe_load(f)

        nats_dep = next((d for d in chart["dependencies"] if d["name"] == "nats"), None)
        self.assertIsNotNone(nats_dep, "NATS dependency not found")
        assert nats_dep is not None  # Type guard for mypy
        self.assertEqual(nats_dep["version"], "~1.3.0")
        self.assertEqual(
            nats_dep["repository"], "https://nats-io.github.io/k8s/helm/charts/"
        )

    def test_subchart_dependencies(self) -> None:
        """Test subchart dependencies are properly configured."""
        with open(self.helm_dir / "Chart.yaml") as f:
            chart = yaml.safe_load(f)

        subcharts = ["monitor-api", "monitor-ui"]
        for subchart in subcharts:
            dep = next(
                (d for d in chart["dependencies"] if d["name"] == subchart), None
            )
            self.assertIsNotNone(dep, f"{subchart} dependency not found")
            assert dep is not None  # Type guard for mypy
            self.assertEqual(dep["repository"], f"file://./charts/{subchart}")


class TestMakefileTargets(unittest.TestCase):
    """Test Makefile targets and automation."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.helm_dir = Path(__file__).parent.parent.parent / "helm"
        self.makefile = self.helm_dir / "Makefile"

    def test_makefile_exists(self) -> None:
        """Test that Makefile exists."""
        self.assertTrue(self.makefile.exists(), "Makefile not found")

    def test_makefile_targets(self) -> None:
        """Test that all required Makefile targets exist."""
        with open(self.makefile) as f:
            content = f.read()

        required_targets = [
            "install:",
            "upgrade:",
            "test:",
            "uninstall:",
            "lint:",
            "template:",
            "status:",
            "clean:",
            "dev-install:",
            "dev-upgrade:",
            "dev-uninstall:",
        ]

        for target in required_targets:
            self.assertIn(target, content, f"Makefile target '{target}' not found")


class TestHelmTests(unittest.TestCase):
    """Test Helm test templates."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.helm_dir = Path(__file__).parent.parent.parent / "helm"
        self.tests_dir = self.helm_dir / "templates" / "tests"

    def test_helm_test_files_exist(self) -> None:
        """Test that Helm test files exist."""
        self.assertTrue(self.tests_dir.exists(), "tests directory not found")

        test_files = [
            "nats-connection-test.yaml",
            "api-health-test.yaml",
            "ui-connectivity-test.yaml",
        ]

        for test_file in test_files:
            test_path = self.tests_dir / test_file
            self.assertTrue(test_path.exists(), f"Test file {test_file} not found")

    def test_helm_test_annotations(self) -> None:
        """Test that Helm test templates have proper annotations."""
        test_files = list(self.tests_dir.glob("*.yaml"))

        for test_file in test_files:
            with open(test_file) as f:
                content = f.read()
                # Handle template syntax by extracting the YAML content
                if content.strip().startswith("{{"):
                    # Skip template conditionals for this test
                    continue
                docs = list(yaml.safe_load_all(content))

            for doc in docs:
                if doc and doc.get("kind") == "Pod":
                    annotations = doc.get("metadata", {}).get("annotations", {})
                    self.assertIn("helm.sh/hook", annotations)
                    self.assertEqual(annotations["helm.sh/hook"], "test")


if __name__ == "__main__":
    unittest.main()
