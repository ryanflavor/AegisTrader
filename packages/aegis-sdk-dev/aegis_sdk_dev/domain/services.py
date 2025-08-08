"""Domain services for aegis-sdk-dev following DDD principles."""

from __future__ import annotations

from typing import Any

from aegis_sdk_dev.domain.models import (
    BootstrapConfig,
    ExecutionResult,
    ProjectTemplate,
    RunConfiguration,
    ServiceConfiguration,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)


class ConfigurationValidator:
    """Domain service for validating service configurations."""

    def validate_service_name(self, name: str) -> ValidationIssue | None:
        """Validate service name according to business rules."""
        if not name or len(name) < 3:
            return ValidationIssue(
                level=ValidationLevel.ERROR,
                category="CONFIG",
                message="Service name is invalid or too short",
                resolution="Provide a meaningful service name (minimum 3 characters)",
                details={"service_name": name},
            )

        if not name.replace("-", "").replace("_", "").isalnum():
            return ValidationIssue(
                level=ValidationLevel.ERROR,
                category="CONFIG",
                message="Service name contains invalid characters",
                resolution="Use only alphanumeric characters, hyphens, and underscores",
                details={"service_name": name},
            )

        return None

    def validate_nats_url(self, url: str) -> ValidationIssue | None:
        """Validate NATS URL format."""
        valid_prefixes = ("nats://", "tls://", "ws://", "wss://")
        if not any(url.startswith(prefix) for prefix in valid_prefixes):
            return ValidationIssue(
                level=ValidationLevel.ERROR,
                category="NATS",
                message=f"Invalid NATS URL format: {url}",
                resolution=f"URL must start with one of: {', '.join(valid_prefixes)}",
                details={"url": url, "valid_prefixes": valid_prefixes},
            )
        return None

    def validate_environment(self, environment: str) -> ValidationIssue | None:
        """Validate environment configuration."""
        valid_envs = {
            "auto",
            "local",
            "kubernetes",
            "development",
            "staging",
            "production",
        }
        if environment not in valid_envs:
            return ValidationIssue(
                level=ValidationLevel.WARNING,
                category="CONFIG",
                message=f"Unknown environment: {environment}",
                resolution=f"Use one of: {', '.join(sorted(valid_envs))}",
                details={
                    "environment": environment,
                    "valid_environments": list(valid_envs),
                },
            )
        return None

    def validate_configuration(self, config: ServiceConfiguration) -> ValidationResult:
        """Perform comprehensive configuration validation."""
        result = ValidationResult(environment=config.environment)

        # Validate service name
        if issue := self.validate_service_name(config.service_name):
            result.add_issue(issue)

        # Validate NATS URL
        if issue := self.validate_nats_url(config.nats_url):
            result.add_issue(issue)

        # Validate environment
        if issue := self.validate_environment(config.environment):
            result.add_issue(issue)

        # Add diagnostics
        result.diagnostics["service_name"] = config.service_name
        result.diagnostics["nats_url"] = config.nats_url
        result.diagnostics["environment"] = config.environment
        result.diagnostics["kv_bucket"] = config.kv_bucket
        result.diagnostics["enable_watchable"] = config.enable_watchable

        # Add recommendations based on issues
        if result.has_errors():
            result.recommendations.append(
                "Fix all ERROR level issues before attempting to start the service"
            )

        if config.environment == "kubernetes" and "localhost" in config.nats_url:
            result.recommendations.append(
                "Consider using Kubernetes service DNS for NATS URL in Kubernetes environment"
            )

        return result


class ProjectGenerator:
    """Domain service for generating project structures."""

    def generate_project_structure(self, config: BootstrapConfig) -> dict[str, str]:
        """Generate project file structure based on template and configuration.

        Returns a mapping of file paths to file contents.
        """
        files = {}

        # Base directory structure
        base_dir = f"{config.output_dir}/{config.project_name}"

        # Always generate main application structure
        files.update(self._generate_application_structure(base_dir, config))

        # Generate tests if requested
        if config.include_tests:
            files.update(self._generate_test_structure(base_dir, config))

        # Generate Docker support if requested
        if config.include_docker:
            files.update(self._generate_docker_files(base_dir, config))

        # Generate Kubernetes manifests if requested
        if config.include_k8s:
            files.update(self._generate_kubernetes_manifests(base_dir, config))

        return files

    def _generate_application_structure(
        self, base_dir: str, config: BootstrapConfig
    ) -> dict[str, str]:
        """Generate core application structure."""
        files = {}

        if config.template == ProjectTemplate.ENTERPRISE_DDD:
            # 企业级DDD架构
            # Domain layer - 核心业务逻辑
            files[f"{base_dir}/domain/__init__.py"] = self._generate_domain_init(config)
            files[f"{base_dir}/domain/entities.py"] = self._generate_domain_entities(config)
            files[f"{base_dir}/domain/value_objects.py"] = self._generate_domain_value_objects(
                config
            )
            files[f"{base_dir}/domain/repositories.py"] = self._generate_domain_repositories(config)
            files[f"{base_dir}/domain/services.py"] = self._generate_domain_services(config)

            # Application layer - 用例编排
            files[f"{base_dir}/application/__init__.py"] = self._generate_application_init(config)
            files[f"{base_dir}/application/commands.py"] = self._generate_commands(config)
            files[f"{base_dir}/application/queries.py"] = self._generate_queries(config)
            files[f"{base_dir}/application/handlers.py"] = self._generate_handlers(config)

            # Infrastructure layer - 基础设施实现
            files[f"{base_dir}/infra/__init__.py"] = self._generate_infra_init(config)
            files[f"{base_dir}/infra/persistence.py"] = self._generate_persistence(config)
            files[f"{base_dir}/infra/messaging.py"] = self._generate_messaging(config)
            files[f"{base_dir}/infra/adapters.py"] = self._generate_adapters(config)

            # Crossdomain layer - 防腐层
            files[f"{base_dir}/crossdomain/__init__.py"] = self._generate_crossdomain_init(config)
            files[f"{base_dir}/crossdomain/translators.py"] = self._generate_translators(config)
            files[f"{base_dir}/crossdomain/anti_corruption.py"] = self._generate_anti_corruption(
                config
            )

            # Package layer - 纯工具函数
            files[f"{base_dir}/pkg/__init__.py"] = self._generate_pkg_init(config)
            files[f"{base_dir}/pkg/utils.py"] = self._generate_utils(config)
            files[f"{base_dir}/pkg/validators.py"] = self._generate_validators(config)

            # Types layer - 类型定义
            files[f"{base_dir}/types/__init__.py"] = self._generate_types_init(config)
            files[f"{base_dir}/types/dto.py"] = self._generate_dto(config)
            files[f"{base_dir}/types/interfaces.py"] = self._generate_interfaces(config)
        else:
            # 标准架构
            # Domain layer
            files[f"{base_dir}/domain/__init__.py"] = self._generate_domain_init(config)
            files[f"{base_dir}/domain/models.py"] = self._generate_domain_models(config)
            files[f"{base_dir}/domain/services.py"] = self._generate_domain_services(config)

            # Application layer
            files[f"{base_dir}/application/__init__.py"] = self._generate_application_init(config)
            files[f"{base_dir}/application/use_cases.py"] = self._generate_use_cases(config)

            # Ports layer
            files[f"{base_dir}/ports/__init__.py"] = self._generate_ports_init(config)
            files[f"{base_dir}/ports/inbound.py"] = self._generate_inbound_ports(config)
            files[f"{base_dir}/ports/outbound.py"] = self._generate_outbound_ports(config)

            # Infrastructure layer
            files[f"{base_dir}/infrastructure/__init__.py"] = self._generate_infrastructure_init(
                config
            )
            files[f"{base_dir}/infrastructure/adapters.py"] = self._generate_adapters(config)
            files[f"{base_dir}/infrastructure/factory.py"] = self._generate_factory(config)

        # Main entry point
        files[f"{base_dir}/main.py"] = self._generate_main(config)

        # Requirements file
        files[f"{base_dir}/requirements.txt"] = self._generate_requirements(config)

        return files

    def _generate_test_structure(self, base_dir: str, config: BootstrapConfig) -> dict[str, str]:
        """Generate test file structure."""
        files = {}

        files[f"{base_dir}/tests/__init__.py"] = f'"""Tests for {config.project_name}.."""'
        files[f"{base_dir}/tests/conftest.py"] = self._generate_test_fixtures(config)
        files[f"{base_dir}/tests/unit/test_domain.py"] = self._generate_domain_tests(config)
        files[f"{base_dir}/tests/unit/test_application.py"] = self._generate_application_tests(
            config
        )
        files[f"{base_dir}/tests/integration/test_service.py"] = self._generate_integration_tests(
            config
        )

        return files

    def _generate_docker_files(self, base_dir: str, config: BootstrapConfig) -> dict[str, str]:
        """Generate Docker-related files."""
        files = {}

        files[f"{base_dir}/Dockerfile"] = self._generate_dockerfile(config)
        files[f"{base_dir}/.dockerignore"] = self._generate_dockerignore()

        return files

    def _generate_kubernetes_manifests(
        self, base_dir: str, config: BootstrapConfig
    ) -> dict[str, str]:
        """Generate Kubernetes manifests."""
        files = {}

        files[f"{base_dir}/k8s/deployment.yaml"] = self._generate_k8s_deployment(config)
        files[f"{base_dir}/k8s/service.yaml"] = self._generate_k8s_service(config)
        files[f"{base_dir}/k8s/configmap.yaml"] = self._generate_k8s_configmap(config)

        return files

    # Template generation methods (simplified for brevity)
    def _generate_domain_init(self, config: BootstrapConfig) -> str:
        return f'"""Domain layer for {config.project_name}."""\n'

    def _generate_domain_models(self, config: BootstrapConfig) -> str:
        return f'"""Domain models for {config.project_name}."""\n\nfrom pydantic import BaseModel\n'

    def _generate_domain_services(self, config: BootstrapConfig) -> str:
        return f'"""Domain services for {config.project_name}."""\n'

    def _generate_application_init(self, config: BootstrapConfig) -> str:
        return f'"""Application layer for {config.project_name}."""\n'

    def _generate_use_cases(self, config: BootstrapConfig) -> str:
        return f'"""Use cases for {config.project_name}."""\n'

    def _generate_ports_init(self, config: BootstrapConfig) -> str:
        return f'"""Ports for {config.project_name}."""\n'

    def _generate_inbound_ports(self, config: BootstrapConfig) -> str:
        return f'"""Inbound ports for {config.project_name}."""\n'

    def _generate_outbound_ports(self, config: BootstrapConfig) -> str:
        return f'"""Outbound ports for {config.project_name}."""\n'

    def _generate_infrastructure_init(self, config: BootstrapConfig) -> str:
        return f'"""Infrastructure layer for {config.project_name}."""\n'

    def _generate_adapters(self, config: BootstrapConfig) -> str:
        return f'"""Infrastructure adapters for {config.project_name}."""\n'

    def _generate_factory(self, config: BootstrapConfig) -> str:
        return '"""Factory for creating application instances."""\n'

    def _generate_main(self, config: BootstrapConfig) -> str:
        return f'"""Main entry point for {config.project_name}."""\n\nif __name__ == "__main__":\n    print("Starting {config.project_name}...")\n'

    def _generate_requirements(self, config: BootstrapConfig) -> str:
        return "aegis-sdk>=1.0.0\npydantic>=2.0.0\nclick>=8.0.0\n"

    def _generate_test_fixtures(self, config: BootstrapConfig) -> str:
        return f'"""Test fixtures for {config.project_name}."""\n\nimport pytest\n'

    def _generate_domain_tests(self, config: BootstrapConfig) -> str:
        return '"""Domain layer tests."""\n\nimport pytest\n'

    def _generate_application_tests(self, config: BootstrapConfig) -> str:
        return '"""Application layer tests."""\n\nimport pytest\n'

    def _generate_integration_tests(self, config: BootstrapConfig) -> str:
        return '"""Integration tests."""\n\nimport pytest\n'

    def _generate_dockerfile(self, config: BootstrapConfig) -> str:
        return """FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
"""

    def _generate_dockerignore(self) -> str:
        return """__pycache__
*.pyc
.pytest_cache
.coverage
*.egg-info
.env
"""

    def _generate_k8s_deployment(self, config: BootstrapConfig) -> str:
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {config.project_name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {config.project_name}
  template:
    metadata:
      labels:
        app: {config.project_name}
    spec:
      containers:
      - name: {config.project_name}
        image: {config.project_name}:latest
"""

    def _generate_k8s_service(self, config: BootstrapConfig) -> str:
        return f"""apiVersion: v1
kind: Service
metadata:
  name: {config.project_name}
spec:
  selector:
    app: {config.project_name}
  ports:
  - port: 80
    targetPort: 8080
"""

    def _generate_k8s_configmap(self, config: BootstrapConfig) -> str:
        return f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {config.project_name}-config
data:
  service.name: {config.project_name}
"""


class TestOrchestrator:
    """Domain service for orchestrating test execution."""

    def prepare_test_environment(self, config: RunConfiguration) -> dict[str, Any]:
        """Prepare the test environment based on configuration."""
        env = {
            "test_type": config.test_type.value,
            "verbose": config.verbose,
            "coverage": config.coverage,
            "min_coverage": config.min_coverage,
            "test_path": config.test_path,
        }

        # Add pytest arguments
        pytest_args = [config.test_path]

        if config.verbose:
            pytest_args.append("-v")

        if config.coverage:
            pytest_args.extend(["--cov", "--cov-report=term-missing"])

        if config.markers:
            for marker in config.markers:
                pytest_args.extend(["-m", marker])

        env["pytest_args"] = pytest_args

        return env

    def analyze_test_results(
        self,
        exit_code: int,
        output: str,
        duration: float,
        config: RunConfiguration,
    ) -> ExecutionResult:
        """Analyze test execution output and create result object."""
        import re

        # Parse test counts from output
        passed = 0
        failed = 0
        skipped = 0
        errors = []

        # Look for pytest summary line
        summary_match = re.search(r"(\d+) passed|(\d+) failed|(\d+) skipped|(\d+) error", output)
        if summary_match:
            if summary_match.group(1):
                passed = int(summary_match.group(1))
            if summary_match.group(2):
                failed = int(summary_match.group(2))
            if summary_match.group(3):
                skipped = int(summary_match.group(3))

        # Parse coverage if enabled
        coverage_percentage = None
        if config.coverage:
            coverage_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
            if coverage_match:
                coverage_percentage = float(coverage_match.group(1))

        # Extract errors
        if exit_code != 0 and "ERROR" in output:
            error_lines = [line for line in output.split("\n") if "ERROR" in line]
            errors = error_lines[:5]  # Limit to first 5 errors

        return ExecutionResult(
            test_type=config.test_type,
            passed=passed,
            failed=failed,
            skipped=skipped,
            coverage_percentage=coverage_percentage,
            duration_seconds=duration,
            errors=errors,
        )

    def validate_test_results(
        self, result: ExecutionResult, config: RunConfiguration
    ) -> list[ValidationIssue]:
        """Validate test results against configured criteria."""
        issues = []

        # Check for test failures
        if result.failed > 0:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="TEST",
                    message=f"{result.failed} test(s) failed",
                    resolution="Fix failing tests before proceeding",
                    details={"failed_count": result.failed, "errors": result.errors},
                )
            )

        # Check coverage threshold
        if (
            config.coverage
            and result.coverage_percentage is not None
            and result.coverage_percentage < config.min_coverage
        ):
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.WARNING,
                    category="COVERAGE",
                    message=f"Coverage {result.coverage_percentage}% is below threshold {config.min_coverage}%",
                    resolution="Add more tests to improve coverage",
                    details={
                        "current_coverage": result.coverage_percentage,
                        "required_coverage": config.min_coverage,
                    },
                )
            )

        # Check for test errors
        if result.errors:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category="TEST",
                    message="Test execution encountered errors",
                    resolution="Review and fix test errors",
                    details={"errors": result.errors},
                )
            )

        return issues
