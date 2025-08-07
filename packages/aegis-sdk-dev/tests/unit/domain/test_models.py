"""Unit tests for domain models."""

import pytest
from pydantic import ValidationError

from aegis_sdk_dev.domain.models import (
    BootstrapConfig,
    ProjectTemplate,
    ServiceConfiguration,
    TestConfiguration,
    TestResult,
    TestType,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)


class TestValidationLevel:
    """Test ValidationLevel enum."""

    def test_validation_levels(self):
        """Test all validation levels are defined."""
        assert ValidationLevel.ERROR == "ERROR"
        assert ValidationLevel.WARNING == "WARNING"
        assert ValidationLevel.INFO == "INFO"


class TestProjectTemplate:
    """Test ProjectTemplate enum."""

    def test_project_templates(self):
        """Test all project templates are defined."""
        assert ProjectTemplate.BASIC == "basic"
        assert ProjectTemplate.SINGLE_ACTIVE == "single_active"
        assert ProjectTemplate.EVENT_DRIVEN == "event_driven"
        assert ProjectTemplate.FULL_FEATURED == "full_featured"


class TestTestType:
    """Test TestType enum."""

    def test_test_types(self):
        """Test all test types are defined."""
        assert TestType.UNIT == "unit"
        assert TestType.INTEGRATION == "integration"
        assert TestType.E2E == "e2e"
        assert TestType.ALL == "all"


class TestValidationIssue:
    """Test ValidationIssue value object."""

    def test_create_valid_issue(self):
        """Test creating a valid validation issue."""
        issue = ValidationIssue(
            level=ValidationLevel.ERROR,
            category="NATS",
            message="Connection failed",
            resolution="Check NATS server",
            details={"url": "nats://localhost:4222"},
        )
        assert issue.level == ValidationLevel.ERROR
        assert issue.category == "NATS"
        assert issue.message == "Connection failed"
        assert issue.resolution == "Check NATS server"
        assert issue.details == {"url": "nats://localhost:4222"}

    def test_category_uppercase(self):
        """Test category is converted to uppercase."""
        issue = ValidationIssue(
            level=ValidationLevel.INFO,
            category="config",
            message="Config info",
        )
        assert issue.category == "CONFIG"

    def test_frozen_model(self):
        """Test ValidationIssue is immutable."""
        issue = ValidationIssue(
            level=ValidationLevel.ERROR,
            category="TEST",
            message="Test message",
        )
        with pytest.raises(ValidationError):
            issue.level = ValidationLevel.WARNING

    def test_optional_fields(self):
        """Test optional fields have proper defaults."""
        issue = ValidationIssue(
            level=ValidationLevel.INFO,
            category="TEST",
            message="Test message",
        )
        assert issue.resolution is None
        assert issue.details == {}


class TestValidationResult:
    """Test ValidationResult aggregate."""

    def test_create_valid_result(self):
        """Test creating a valid validation result."""
        result = ValidationResult(environment="local")
        assert result.is_valid is True
        assert result.environment == "local"
        assert result.issues == []
        assert result.diagnostics == {}
        assert result.recommendations == []

    def test_add_issue(self):
        """Test adding issues to result."""
        result = ValidationResult(environment="test")
        issue = ValidationIssue(
            level=ValidationLevel.WARNING,
            category="TEST",
            message="Test warning",
        )
        result.add_issue(issue)
        assert len(result.issues) == 1
        assert result.issues[0] == issue
        assert result.is_valid is True  # Warnings don't invalidate

    def test_add_error_issue(self):
        """Test adding error issue invalidates result."""
        result = ValidationResult(environment="test")
        issue = ValidationIssue(
            level=ValidationLevel.ERROR,
            category="TEST",
            message="Test error",
        )
        result.add_issue(issue)
        assert result.is_valid is False

    def test_get_issues_by_level(self):
        """Test filtering issues by level."""
        result = ValidationResult(environment="test")
        error = ValidationIssue(level=ValidationLevel.ERROR, category="TEST", message="Error")
        warning = ValidationIssue(level=ValidationLevel.WARNING, category="TEST", message="Warning")
        info = ValidationIssue(level=ValidationLevel.INFO, category="TEST", message="Info")

        result.add_issue(error)
        result.add_issue(warning)
        result.add_issue(info)

        assert len(result.get_issues_by_level(ValidationLevel.ERROR)) == 1
        assert len(result.get_issues_by_level(ValidationLevel.WARNING)) == 1
        assert len(result.get_issues_by_level(ValidationLevel.INFO)) == 1

    def test_get_issues_by_category(self):
        """Test filtering issues by category."""
        result = ValidationResult(environment="test")
        nats_issue = ValidationIssue(
            level=ValidationLevel.ERROR, category="NATS", message="NATS error"
        )
        config_issue = ValidationIssue(
            level=ValidationLevel.WARNING, category="CONFIG", message="Config warning"
        )

        result.add_issue(nats_issue)
        result.add_issue(config_issue)

        assert len(result.get_issues_by_category("NATS")) == 1
        assert len(result.get_issues_by_category("CONFIG")) == 1
        assert len(result.get_issues_by_category("OTHER")) == 0

    def test_has_errors(self):
        """Test checking for errors."""
        result = ValidationResult(environment="test")
        assert result.has_errors() is False

        result.add_issue(
            ValidationIssue(level=ValidationLevel.WARNING, category="TEST", message="Warning")
        )
        assert result.has_errors() is False

        result.add_issue(
            ValidationIssue(level=ValidationLevel.ERROR, category="TEST", message="Error")
        )
        assert result.has_errors() is True

    def test_has_warnings(self):
        """Test checking for warnings."""
        result = ValidationResult(environment="test")
        assert result.has_warnings() is False

        result.add_issue(
            ValidationIssue(level=ValidationLevel.INFO, category="TEST", message="Info")
        )
        assert result.has_warnings() is False

        result.add_issue(
            ValidationIssue(level=ValidationLevel.WARNING, category="TEST", message="Warning")
        )
        assert result.has_warnings() is True


class TestServiceConfiguration:
    """Test ServiceConfiguration entity."""

    def test_create_valid_config(self):
        """Test creating a valid service configuration."""
        config = ServiceConfiguration(
            service_name="test-service",
            nats_url="nats://localhost:4222",
            environment="local",
        )
        assert config.service_name == "test-service"
        assert config.nats_url == "nats://localhost:4222"
        assert config.environment == "local"
        assert config.kv_bucket == "service_registry"
        assert config.enable_watchable is True
        assert config.debug is False

    def test_invalid_service_name(self):
        """Test validation of service name."""
        with pytest.raises(ValidationError):
            ServiceConfiguration(
                service_name="",  # Empty name not allowed
                nats_url="nats://localhost:4222",
            )

    def test_invalid_nats_url(self):
        """Test validation of NATS URL."""
        with pytest.raises(ValidationError):
            ServiceConfiguration(
                service_name="test",
                nats_url="http://localhost:4222",  # Invalid protocol
            )

    def test_valid_nats_url_protocols(self):
        """Test all valid NATS URL protocols."""
        protocols = ["nats://", "tls://", "ws://", "wss://"]
        for protocol in protocols:
            config = ServiceConfiguration(
                service_name="test",
                nats_url=f"{protocol}localhost:4222",
            )
            assert config.nats_url.startswith(protocol)

    def test_invalid_environment(self):
        """Test validation of environment."""
        with pytest.raises(ValidationError):
            ServiceConfiguration(
                service_name="test",
                nats_url="nats://localhost:4222",
                environment="invalid",
            )

    def test_valid_environments(self):
        """Test all valid environments."""
        environments = ["auto", "local", "kubernetes", "development", "staging", "production"]
        for env in environments:
            config = ServiceConfiguration(
                service_name="test",
                nats_url="nats://localhost:4222",
                environment=env,
            )
            assert config.environment == env


class TestBootstrapConfig:
    """Test BootstrapConfig value object."""

    def test_create_valid_config(self):
        """Test creating a valid bootstrap configuration."""
        service_config = ServiceConfiguration(
            service_name="test",
            nats_url="nats://localhost:4222",
        )
        config = BootstrapConfig(
            project_name="test-project",
            template=ProjectTemplate.BASIC,
            service_config=service_config,
        )
        assert config.project_name == "test-project"
        assert config.template == ProjectTemplate.BASIC
        assert config.service_config == service_config
        assert config.output_dir == "."
        assert config.include_tests is True
        assert config.include_docker is True
        assert config.include_k8s is False

    def test_invalid_project_name(self):
        """Test validation of project name."""
        service_config = ServiceConfiguration(
            service_name="test",
            nats_url="nats://localhost:4222",
        )
        with pytest.raises(ValidationError):
            BootstrapConfig(
                project_name="Test Project",  # Spaces not allowed
                template=ProjectTemplate.BASIC,
                service_config=service_config,
            )

    def test_valid_project_names(self):
        """Test valid project name formats."""
        service_config = ServiceConfiguration(
            service_name="test",
            nats_url="nats://localhost:4222",
        )
        valid_names = ["myproject", "my-project", "project123", "test-service-1"]
        for name in valid_names:
            config = BootstrapConfig(
                project_name=name,
                template=ProjectTemplate.BASIC,
                service_config=service_config,
            )
            assert config.project_name == name

    def test_frozen_config(self):
        """Test BootstrapConfig is immutable."""
        service_config = ServiceConfiguration(
            service_name="test",
            nats_url="nats://localhost:4222",
        )
        config = BootstrapConfig(
            project_name="test",
            template=ProjectTemplate.BASIC,
            service_config=service_config,
        )
        with pytest.raises(ValidationError):
            config.project_name = "new-name"


class TestTestConfiguration:
    """Test TestConfiguration value object."""

    def test_create_valid_config(self):
        """Test creating a valid test configuration."""
        config = TestConfiguration(
            test_type=TestType.UNIT,
            verbose=True,
            coverage=True,
            min_coverage=90.0,
        )
        assert config.test_type == TestType.UNIT
        assert config.verbose is True
        assert config.coverage is True
        assert config.min_coverage == 90.0
        assert config.test_path == "tests"
        assert config.markers == []

    def test_coverage_bounds(self):
        """Test coverage percentage bounds."""
        with pytest.raises(ValidationError):
            TestConfiguration(
                test_type=TestType.ALL,
                min_coverage=-1.0,  # Below minimum
            )

        with pytest.raises(ValidationError):
            TestConfiguration(
                test_type=TestType.ALL,
                min_coverage=101.0,  # Above maximum
            )

    def test_frozen_config(self):
        """Test TestConfiguration is immutable."""
        config = TestConfiguration(test_type=TestType.UNIT)
        with pytest.raises(ValidationError):
            config.verbose = True


class TestTestResult:
    """Test TestResult value object."""

    def test_create_valid_result(self):
        """Test creating a valid test result."""
        result = TestResult(
            test_type=TestType.UNIT,
            passed=10,
            failed=2,
            skipped=1,
            coverage_percentage=85.5,
            duration_seconds=5.3,
        )
        assert result.test_type == TestType.UNIT
        assert result.passed == 10
        assert result.failed == 2
        assert result.skipped == 1
        assert result.coverage_percentage == 85.5
        assert result.duration_seconds == 5.3
        assert result.errors == []

    def test_total_tests(self):
        """Test total tests calculation."""
        result = TestResult(
            test_type=TestType.ALL,
            passed=10,
            failed=2,
            skipped=3,
            duration_seconds=1.0,
        )
        assert result.total_tests == 15

    def test_success_rate(self):
        """Test success rate calculation."""
        result = TestResult(
            test_type=TestType.UNIT,
            passed=8,
            failed=2,
            skipped=0,
            duration_seconds=1.0,
        )
        assert result.success_rate == 80.0

    def test_success_rate_no_tests(self):
        """Test success rate with no tests."""
        result = TestResult(
            test_type=TestType.UNIT,
            passed=0,
            failed=0,
            skipped=0,
            duration_seconds=0.1,
        )
        assert result.success_rate == 0.0

    def test_is_successful(self):
        """Test checking if test run was successful."""
        # Successful result
        result = TestResult(
            test_type=TestType.UNIT,
            passed=10,
            failed=0,
            duration_seconds=1.0,
        )
        assert result.is_successful() is True

        # Failed tests
        result = TestResult(
            test_type=TestType.UNIT,
            passed=10,
            failed=1,
            duration_seconds=1.0,
        )
        assert result.is_successful() is False

        # With errors
        result = TestResult(
            test_type=TestType.UNIT,
            passed=10,
            failed=0,
            duration_seconds=1.0,
            errors=["Import error"],
        )
        assert result.is_successful() is False

    def test_frozen_result(self):
        """Test TestResult is immutable."""
        result = TestResult(
            test_type=TestType.UNIT,
            duration_seconds=1.0,
        )
        with pytest.raises(ValidationError):
            result.passed = 10
