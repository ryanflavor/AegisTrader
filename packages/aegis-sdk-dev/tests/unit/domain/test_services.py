"""Unit tests for domain services."""

from aegis_sdk_dev.domain.models import (
    BootstrapConfig,
    ProjectTemplate,
    ServiceConfiguration,
    TestConfiguration,
    TestType,
    ValidationLevel,
)
from aegis_sdk_dev.domain.services import (
    ConfigurationValidator,
    ProjectGenerator,
    TestOrchestrator,
)


class TestConfigurationValidator:
    """Test ConfigurationValidator domain service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ConfigurationValidator()

    def test_validate_service_name_valid(self):
        """Test validation of valid service names."""
        valid_names = ["test-service", "my_service", "service123", "test-svc-1"]
        for name in valid_names:
            issue = self.validator.validate_service_name(name)
            assert issue is None

    def test_validate_service_name_too_short(self):
        """Test validation of short service names."""
        issue = self.validator.validate_service_name("ab")
        assert issue is not None
        assert issue.level == ValidationLevel.ERROR
        assert issue.category == "CONFIG"
        assert "too short" in issue.message

    def test_validate_service_name_empty(self):
        """Test validation of empty service name."""
        issue = self.validator.validate_service_name("")
        assert issue is not None
        assert issue.level == ValidationLevel.ERROR

    def test_validate_service_name_invalid_chars(self):
        """Test validation of service names with invalid characters."""
        issue = self.validator.validate_service_name("test@service")
        assert issue is not None
        assert issue.level == ValidationLevel.ERROR
        assert "invalid characters" in issue.message

    def test_validate_nats_url_valid(self):
        """Test validation of valid NATS URLs."""
        valid_urls = [
            "nats://localhost:4222",
            "tls://secure.nats.io:4222",
            "ws://localhost:8080",
            "wss://secure.nats.io:443",
        ]
        for url in valid_urls:
            issue = self.validator.validate_nats_url(url)
            assert issue is None

    def test_validate_nats_url_invalid(self):
        """Test validation of invalid NATS URLs."""
        issue = self.validator.validate_nats_url("http://localhost:4222")
        assert issue is not None
        assert issue.level == ValidationLevel.ERROR
        assert issue.category == "NATS"

    def test_validate_environment_valid(self):
        """Test validation of valid environments."""
        valid_envs = ["auto", "local", "kubernetes", "development", "staging", "production"]
        for env in valid_envs:
            issue = self.validator.validate_environment(env)
            assert issue is None

    def test_validate_environment_invalid(self):
        """Test validation of invalid environment."""
        issue = self.validator.validate_environment("unknown")
        assert issue is not None
        assert issue.level == ValidationLevel.WARNING
        assert issue.category == "CONFIG"

    def test_validate_configuration_comprehensive(self):
        """Test comprehensive configuration validation."""
        config = ServiceConfiguration(
            service_name="test-service",
            nats_url="nats://localhost:4222",
            environment="local",
        )
        result = self.validator.validate_configuration(config)

        assert result.is_valid is True
        assert len(result.issues) == 0
        assert result.diagnostics["service_name"] == "test-service"
        assert result.diagnostics["nats_url"] == "nats://localhost:4222"
        assert result.diagnostics["environment"] == "local"

    def test_validate_configuration_with_errors(self):
        """Test configuration validation with errors."""
        config = ServiceConfiguration(
            service_name="ab",  # Too short
            nats_url="http://localhost:4222",  # Invalid protocol
            environment="local",
        )
        result = self.validator.validate_configuration(config)

        assert result.is_valid is False
        assert len(result.issues) >= 2
        assert result.has_errors() is True

    def test_validate_configuration_recommendations(self):
        """Test configuration validation adds recommendations."""
        config = ServiceConfiguration(
            service_name="test",
            nats_url="nats://localhost:4222",
            environment="kubernetes",
        )
        result = self.validator.validate_configuration(config)

        # Should have recommendation about localhost in k8s
        assert len(result.recommendations) > 0
        assert any("Kubernetes" in rec for rec in result.recommendations)


class TestProjectGenerator:
    """Test ProjectGenerator domain service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = ProjectGenerator()

    def test_generate_project_structure_basic(self):
        """Test generating basic project structure."""
        service_config = ServiceConfiguration(
            service_name="test-service",
            nats_url="nats://localhost:4222",
        )
        config = BootstrapConfig(
            project_name="test-project",
            template=ProjectTemplate.BASIC,
            service_config=service_config,
            include_tests=False,
            include_docker=False,
            include_k8s=False,
        )

        files = self.generator.generate_project_structure(config)

        # Check core files are generated
        assert "test-project/domain/__init__.py" in files
        assert "test-project/application/__init__.py" in files
        assert "test-project/ports/__init__.py" in files
        assert "test-project/infrastructure/__init__.py" in files
        assert "test-project/main.py" in files
        assert "test-project/requirements.txt" in files

        # Check tests are not included
        assert not any("tests" in path for path in files.keys())

    def test_generate_project_structure_with_tests(self):
        """Test generating project structure with tests."""
        service_config = ServiceConfiguration(
            service_name="test-service",
            nats_url="nats://localhost:4222",
        )
        config = BootstrapConfig(
            project_name="test-project",
            template=ProjectTemplate.BASIC,
            service_config=service_config,
            include_tests=True,
            include_docker=False,
            include_k8s=False,
        )

        files = self.generator.generate_project_structure(config)

        # Check test files are generated
        assert "test-project/tests/__init__.py" in files
        assert "test-project/tests/conftest.py" in files
        assert "test-project/tests/unit/test_domain.py" in files
        assert "test-project/tests/unit/test_application.py" in files
        assert "test-project/tests/integration/test_service.py" in files

    def test_generate_project_structure_with_docker(self):
        """Test generating project structure with Docker support."""
        service_config = ServiceConfiguration(
            service_name="test-service",
            nats_url="nats://localhost:4222",
        )
        config = BootstrapConfig(
            project_name="test-project",
            template=ProjectTemplate.BASIC,
            service_config=service_config,
            include_tests=False,
            include_docker=True,
            include_k8s=False,
        )

        files = self.generator.generate_project_structure(config)

        # Check Docker files are generated
        assert "test-project/Dockerfile" in files
        assert "test-project/.dockerignore" in files

    def test_generate_project_structure_with_k8s(self):
        """Test generating project structure with Kubernetes manifests."""
        service_config = ServiceConfiguration(
            service_name="test-service",
            nats_url="nats://localhost:4222",
        )
        config = BootstrapConfig(
            project_name="test-project",
            template=ProjectTemplate.BASIC,
            service_config=service_config,
            include_tests=False,
            include_docker=False,
            include_k8s=True,
        )

        files = self.generator.generate_project_structure(config)

        # Check Kubernetes manifests are generated
        assert "test-project/k8s/deployment.yaml" in files
        assert "test-project/k8s/service.yaml" in files
        assert "test-project/k8s/configmap.yaml" in files

    def test_generate_project_custom_output_dir(self):
        """Test generating project with custom output directory."""
        service_config = ServiceConfiguration(
            service_name="test-service",
            nats_url="nats://localhost:4222",
        )
        config = BootstrapConfig(
            project_name="test-project",
            template=ProjectTemplate.BASIC,
            service_config=service_config,
            output_dir="/custom/path",
            include_tests=False,
            include_docker=False,
            include_k8s=False,
        )

        files = self.generator.generate_project_structure(config)

        # Check files use custom output directory
        assert all(path.startswith("/custom/path/test-project/") for path in files.keys())


class TestTestOrchestrator:
    """Test TestOrchestrator domain service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.orchestrator = TestOrchestrator()

    def test_prepare_test_environment_basic(self):
        """Test preparing basic test environment."""
        config = TestConfiguration(
            test_type=TestType.UNIT,
            verbose=False,
            coverage=False,
        )

        env = self.orchestrator.prepare_test_environment(config)

        assert env["test_type"] == "unit"
        assert env["verbose"] is False
        assert env["coverage"] is False
        assert "pytest_args" in env
        assert config.test_path in env["pytest_args"]

    def test_prepare_test_environment_verbose(self):
        """Test preparing test environment with verbose output."""
        config = TestConfiguration(
            test_type=TestType.UNIT,
            verbose=True,
            coverage=False,
        )

        env = self.orchestrator.prepare_test_environment(config)

        assert env["verbose"] is True
        assert "-v" in env["pytest_args"]

    def test_prepare_test_environment_coverage(self):
        """Test preparing test environment with coverage."""
        config = TestConfiguration(
            test_type=TestType.UNIT,
            verbose=False,
            coverage=True,
        )

        env = self.orchestrator.prepare_test_environment(config)

        assert env["coverage"] is True
        assert "--cov" in env["pytest_args"]
        assert "--cov-report=term-missing" in env["pytest_args"]

    def test_prepare_test_environment_with_markers(self):
        """Test preparing test environment with markers."""
        config = TestConfiguration(
            test_type=TestType.UNIT,
            markers=["slow", "network"],
        )

        env = self.orchestrator.prepare_test_environment(config)

        pytest_args = env["pytest_args"]
        assert "-m" in pytest_args
        assert "slow" in pytest_args
        assert "network" in pytest_args

    def test_analyze_test_results_success(self):
        """Test analyzing successful test results."""
        config = TestConfiguration(test_type=TestType.UNIT)
        output = "10 passed in 2.50s"

        result = self.orchestrator.analyze_test_results(
            exit_code=0,
            output=output,
            duration=2.5,
            config=config,
        )

        assert result.test_type == TestType.UNIT
        assert result.passed == 10
        assert result.failed == 0
        assert result.duration_seconds == 2.5
        assert result.is_successful() is True

    def test_analyze_test_results_with_failures(self):
        """Test analyzing test results with failures."""
        config = TestConfiguration(test_type=TestType.INTEGRATION)
        output = "8 passed, 2 failed in 5.00s"

        result = self.orchestrator.analyze_test_results(
            exit_code=1,
            output=output,
            duration=5.0,
            config=config,
        )

        assert result.test_type == TestType.INTEGRATION
        assert result.passed == 8
        assert result.failed == 2
        assert result.duration_seconds == 5.0
        assert result.is_successful() is False

    def test_analyze_test_results_with_coverage(self):
        """Test analyzing test results with coverage."""
        config = TestConfiguration(test_type=TestType.ALL, coverage=True)
        output = """
        10 passed in 3.00s
        TOTAL     100      10      90%
        """

        result = self.orchestrator.analyze_test_results(
            exit_code=0,
            output=output,
            duration=3.0,
            config=config,
        )

        assert result.coverage_percentage == 90.0

    def test_validate_test_results_success(self):
        """Test validating successful test results."""
        config = TestConfiguration(
            test_type=TestType.UNIT,
            coverage=True,
            min_coverage=80.0,
        )
        result = TestResult(
            test_type=TestType.UNIT,
            passed=10,
            failed=0,
            coverage_percentage=85.0,
            duration_seconds=2.0,
        )

        issues = self.orchestrator.validate_test_results(result, config)

        assert len(issues) == 0

    def test_validate_test_results_with_failures(self):
        """Test validating test results with failures."""
        config = TestConfiguration(test_type=TestType.UNIT)
        result = TestResult(
            test_type=TestType.UNIT,
            passed=8,
            failed=2,
            duration_seconds=2.0,
        )

        issues = self.orchestrator.validate_test_results(result, config)

        assert len(issues) > 0
        assert any(issue.level == ValidationLevel.ERROR for issue in issues)
        assert any("failed" in issue.message for issue in issues)

    def test_validate_test_results_low_coverage(self):
        """Test validating test results with low coverage."""
        config = TestConfiguration(
            test_type=TestType.UNIT,
            coverage=True,
            min_coverage=90.0,
        )
        result = TestResult(
            test_type=TestType.UNIT,
            passed=10,
            failed=0,
            coverage_percentage=75.0,
            duration_seconds=2.0,
        )

        issues = self.orchestrator.validate_test_results(result, config)

        assert len(issues) > 0
        assert any(issue.level == ValidationLevel.WARNING for issue in issues)
        assert any("coverage" in issue.message.lower() for issue in issues)

    def test_validate_test_results_with_errors(self):
        """Test validating test results with errors."""
        config = TestConfiguration(test_type=TestType.UNIT)
        result = TestResult(
            test_type=TestType.UNIT,
            passed=0,
            failed=0,
            duration_seconds=0.1,
            errors=["Import error: module not found"],
        )

        issues = self.orchestrator.validate_test_results(result, config)

        assert len(issues) > 0
        assert any(issue.level == ValidationLevel.ERROR for issue in issues)
        assert any("errors" in issue.message.lower() for issue in issues)
