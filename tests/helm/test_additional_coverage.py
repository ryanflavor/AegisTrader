#!/usr/bin/env python3
"""
Additional test coverage for AegisTrader Helm charts using pytest.
Focuses on TDD green/blue phase validation and comprehensive coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


class TestHelmHelpers:
    """Test Helm helper templates functionality."""

    @pytest.fixture
    def helm_dir(self) -> Path:
        """Get helm directory path."""
        return Path(__file__).parent.parent.parent / "helm"

    def test_helpers_template_exists(self, helm_dir: Path) -> None:
        """Test that _helpers.tpl exists with required functions."""
        helpers_file = helm_dir / "templates" / "_helpers.tpl"
        assert helpers_file.exists(), "_helpers.tpl not found"

        content = helpers_file.read_text()

        # Check for required helper functions
        required_helpers = [
            "aegis-trader.name",
            "aegis-trader.fullname",
            "aegis-trader.chart",
            "aegis-trader.labels",
            "aegis-trader.selectorLabels",
            "aegis-trader.natsUrl",
            "aegis-trader.monitorApiUrl",
        ]

        for helper in required_helpers:
            assert f'define "{helper}"' in content, f"Helper {helper} not found"

    def test_nats_url_helper_format(self, helm_dir: Path) -> None:
        """Test NATS URL helper generates correct format."""
        helpers_file = helm_dir / "templates" / "_helpers.tpl"
        content = helpers_file.read_text()

        # Extract NATS URL helper section
        nats_section = content[content.find('define "aegis-trader.natsUrl"') :]
        assert "nats://" in nats_section
        # Check template format
        assert 'printf "nats://%s-nats:%v"' in nats_section
        assert "$natsPort" in nats_section

    def test_monitor_api_url_helper(self, helm_dir: Path) -> None:
        """Test Monitor API URL helper format."""
        helpers_file = helm_dir / "templates" / "_helpers.tpl"
        content = helpers_file.read_text()

        # Extract API URL helper section
        api_section = content[content.find('define "aegis-trader.monitorApiUrl"') :]
        assert "http://" in api_section
        # Check template format
        assert 'printf "http://%s-monitor-api:%d"' in api_section
        assert "$apiPort" in api_section


class TestConfigMapTemplates:
    """Test ConfigMap template rendering."""

    @pytest.fixture
    def helm_dir(self) -> Path:
        """Get helm directory path."""
        return Path(__file__).parent.parent.parent / "helm"

    def test_monitor_api_configmap_structure(self, helm_dir: Path) -> None:
        """Test that monitor-api ConfigMap has correct structure."""
        api_configmap = helm_dir / "charts" / "monitor-api" / "templates" / "configmap.yaml"
        assert api_configmap.exists(), "monitor-api ConfigMap not found"

        content = api_configmap.read_text()

        # Verify ConfigMap structure
        assert "kind: ConfigMap" in content
        assert "data:" in content
        assert "{{- range $key, $value := .Values.env }}" in content

    def test_environment_variable_templating(self, helm_dir: Path) -> None:
        """Test environment variables are properly templated."""
        api_configmap = helm_dir / "charts" / "monitor-api" / "templates" / "configmap.yaml"
        content = api_configmap.read_text()

        # Check for proper templating
        assert "{{- range $key, $value := .Values.env }}" in content
        assert "{{ $key }}: {{ $value | quote }}" in content


class TestServiceTemplates:
    """Test Service template configurations."""

    @pytest.fixture
    def helm_dir(self) -> Path:
        """Get helm directory path."""
        return Path(__file__).parent.parent.parent / "helm"

    @pytest.mark.parametrize(
        "service_name,expected_port",
        [
            ("monitor-api", 8100),
            ("monitor-ui", 3100),
        ],
    )
    def test_service_ports_configuration(
        self, helm_dir: Path, service_name: str, expected_port: int
    ) -> None:
        """Test that services expose correct ports."""
        service_file = helm_dir / "charts" / service_name / "templates" / "service.yaml"
        assert service_file.exists(), f"{service_name} service template not found"

        content = service_file.read_text()

        # Check port configuration
        assert "port: {{ .Values.service.port }}" in content
        assert "targetPort: http" in content
        assert "protocol: TCP" in content

    def test_service_selector_labels(self, helm_dir: Path) -> None:
        """Test service selector labels are properly configured."""
        for service in ["monitor-api", "monitor-ui"]:
            service_file = helm_dir / "charts" / service / "templates" / "service.yaml"
            content = service_file.read_text()

            # Check selector labels
            assert "selector:" in content
            assert f'include "{service}.selectorLabels"' in content


class TestDeploymentAdvanced:
    """Test advanced deployment configurations."""

    @pytest.fixture
    def helm_dir(self) -> Path:
        """Get helm directory path."""
        return Path(__file__).parent.parent.parent / "helm"

    def test_resource_limits_match_requests(self, helm_dir: Path) -> None:
        """Test that resource limits match requests for predictable performance."""
        for service in ["monitor-api", "monitor-ui"]:
            # Resources are defined in subchart values
            values_file = helm_dir / "charts" / service / "values.yaml"
            with open(values_file) as f:
                values = yaml.safe_load(f)

            resources = values["resources"]
            assert resources["requests"]["cpu"] == resources["limits"]["cpu"]
            assert resources["requests"]["memory"] == resources["limits"]["memory"]

    def test_probe_configuration_completeness(self, helm_dir: Path) -> None:
        """Test all required probes are configured."""
        # Monitor API should have all three probes
        api_values_file = helm_dir / "charts" / "monitor-api" / "values.yaml"
        with open(api_values_file) as f:
            api_values = yaml.safe_load(f)

        api_probes = api_values["probes"]
        assert api_probes["liveness"]["enabled"] is True
        assert api_probes["readiness"]["enabled"] is True
        assert api_probes["startup"]["enabled"] is True
        assert api_probes["startup"]["failureThreshold"] == 60

        # Monitor UI should have liveness and readiness
        ui_values_file = helm_dir / "charts" / "monitor-ui" / "values.yaml"
        with open(ui_values_file) as f:
            ui_values = yaml.safe_load(f)

        ui_probes = ui_values["probes"]
        assert ui_probes["liveness"]["enabled"] is True
        assert ui_probes["readiness"]["enabled"] is True

    @pytest.mark.parametrize(
        "service,init_container,wait_for",
        [
            ("monitor-api", "wait-for-nats", "nats"),
            ("monitor-ui", "wait-for-api", "monitor-api"),
        ],
    )
    def test_init_container_wait_logic(
        self, helm_dir: Path, service: str, init_container: str, wait_for: str
    ) -> None:
        """Test init containers have proper wait logic."""
        deployment_file = helm_dir / "charts" / service / "templates" / "deployment.yaml"
        content = deployment_file.read_text()

        # Check init container configuration
        assert "initContainers:" in content
        assert f"name: {init_container}" in content
        assert "busybox:" in content  # Any busybox version
        assert "nc -z" in content  # netcat for connection check
        assert wait_for in content


class TestNATSConfiguration:
    """Test NATS-specific configurations."""

    @pytest.fixture
    def helm_dir(self) -> Path:
        """Get helm directory path."""
        return Path(__file__).parent.parent.parent / "helm"

    def test_nats_jetstream_configuration(self, helm_dir: Path) -> None:
        """Test NATS JetStream is properly configured."""
        values_file = helm_dir / "values.yaml"
        with open(values_file) as f:
            values = yaml.safe_load(f)

        nats_config = values["nats"]["nats"]["jetstream"]
        assert nats_config["enabled"] is True
        assert nats_config["fileStorage"]["enabled"] is True
        assert nats_config["fileStorage"]["size"] == "10Gi"

    def test_nats_memory_efficiency(self, helm_dir: Path) -> None:
        """Test NATS memory configuration for efficiency."""
        values_file = helm_dir / "values.yaml"
        with open(values_file) as f:
            values = yaml.safe_load(f)

        # Check GOMEMLIMIT is set for efficiency
        assert values["nats"]["container"]["env"]["GOMEMLIMIT"] == "7GiB"

        # Verify it's ~90% of memory limit
        memory_limit = values["nats"]["container"]["merge"]["resources"]["limits"]["memory"]
        assert memory_limit == "8Gi"

    def test_nats_topology_constraints(self, helm_dir: Path) -> None:
        """Test NATS pod topology spread for HA."""
        values_file = helm_dir / "values.yaml"
        with open(values_file) as f:
            values = yaml.safe_load(f)

        constraints = values["nats"]["podTemplate"]["topologySpreadConstraints"]
        assert "kubernetes.io/hostname" in constraints
        assert constraints["kubernetes.io/hostname"]["maxSkew"] == 1
        assert constraints["kubernetes.io/hostname"]["whenUnsatisfiable"] == "DoNotSchedule"


class TestServiceRegistry:
    """Test service registry KV bucket configuration."""

    @pytest.fixture
    def helm_dir(self) -> Path:
        """Get helm directory path."""
        return Path(__file__).parent.parent.parent / "helm"

    def test_kv_bucket_configuration(self, helm_dir: Path) -> None:
        """Test KV bucket configuration for service registry."""
        values_file = helm_dir / "values.yaml"
        with open(values_file) as f:
            values = yaml.safe_load(f)

        sr_config = values["serviceRegistry"]
        assert sr_config["createBucket"] is True
        assert sr_config["bucketName"] == "service-registry"
        assert sr_config["bucket"]["replicas"] == 3
        assert sr_config["bucket"]["maxBytes"] == 1073741824  # 1GB

    def test_kv_job_helm_hooks(self, helm_dir: Path) -> None:
        """Test KV creation job configuration."""
        kv_job_file = helm_dir / "templates" / "nats-kv-job.yaml"
        content = kv_job_file.read_text()

        # Check job configuration (no hooks to avoid circular dependency)
        assert "kind: Job" in content
        assert "restartPolicy: OnFailure" in content
        # Verify comment explaining why hooks were removed
        assert "Removed helm hooks to avoid circular dependency with --wait" in content

    def test_kv_job_idempotency(self, helm_dir: Path) -> None:
        """Test KV creation job is idempotent."""
        kv_job_file = helm_dir / "templates" / "nats-kv-job.yaml"
        content = kv_job_file.read_text()

        # Check job checks if bucket exists before creating
        assert "nats kv ls" in content
        assert "grep -q" in content
        assert "already exists" in content


class TestMakefileTargets:
    """Test Makefile target completeness and correctness."""

    @pytest.fixture
    def makefile(self) -> Path:
        """Get Makefile path."""
        return Path(__file__).parent.parent.parent / "helm" / "Makefile"

    def test_makefile_help_target(self, makefile: Path) -> None:
        """Test Makefile has comprehensive help."""
        content = makefile.read_text()

        assert "help:" in content
        assert "## Show this help message" in content
        assert "awk" in content  # Used for formatting help

    def test_makefile_safety_features(self, makefile: Path) -> None:
        """Test Makefile has safety features."""
        content = makefile.read_text()

        # Check for dry-run support
        assert "dry-run:" in content
        assert "--dry-run" in content

        # Check for namespace safety
        assert "NAMESPACE ?=" in content
        assert "--namespace $(NAMESPACE)" in content

    def test_makefile_dependencies(self, makefile: Path) -> None:
        """Test Makefile targets have proper dependencies."""
        content = makefile.read_text()

        # Install should check tools, create namespace, update deps, and lint
        assert "install: check-tools create-namespace helm-deps lint" in content

        # Clean should uninstall first
        assert "clean: uninstall" in content


class TestDeploymentValidation:
    """Test deployment validation scripts."""

    @pytest.fixture
    def helm_dir(self) -> Path:
        """Get helm directory path."""
        return Path(__file__).parent.parent.parent / "helm"

    def test_validation_script_exists(self, helm_dir: Path) -> None:
        """Test validation script exists and is executable."""
        script = helm_dir / "scripts" / "validate-deployment.sh"
        assert script.exists()
        assert script.stat().st_mode & 0o111  # Check executable bit

    def test_deployment_simulation_script(self, helm_dir: Path) -> None:
        """Test deployment simulation script for CI environments."""
        script = helm_dir / "test-deployment.sh"
        assert script.exists()
        assert script.stat().st_mode & 0o111

        content = script.read_text()
        # Check it handles both real and simulated environments
        assert "kubectl cluster-info" in content
        assert "simulation mode" in content


class TestNamespaceHandling:
    """Test namespace creation and management."""

    @pytest.fixture
    def helm_dir(self) -> Path:
        """Get helm directory path."""
        return Path(__file__).parent.parent.parent / "helm"

    def test_namespace_template(self, helm_dir: Path) -> None:
        """Test namespace template exists and has labels."""
        namespace_file = helm_dir / "templates" / "namespace.yaml"
        content = namespace_file.read_text()

        assert "kind: Namespace" in content
        assert "app.kubernetes.io/part-of: aegis-trader" in content
        assert "{{- if .Values.createNamespace" in content


class TestHelmTestSuite:
    """Test Helm test suite completeness."""

    @pytest.fixture
    def helm_dir(self) -> Path:
        """Get helm directory path."""
        return Path(__file__).parent.parent.parent / "helm"

    @pytest.mark.parametrize(
        "test_name,test_description",
        [
            ("nats-connection-test", "NATS connectivity"),
            ("api-health-test", "API health check"),
            ("ui-connectivity-test", "UI to API connectivity"),
        ],
    )
    def test_helm_test_coverage(
        self, helm_dir: Path, test_name: str, test_description: str
    ) -> None:
        """Test Helm test files cover all critical paths."""
        test_file = helm_dir / "templates" / "tests" / f"{test_name}.yaml"
        assert test_file.exists(), f"{test_description} test not found"

        content = test_file.read_text()
        assert '"helm.sh/hook": test' in content
        assert "restartPolicy: Never" in content
