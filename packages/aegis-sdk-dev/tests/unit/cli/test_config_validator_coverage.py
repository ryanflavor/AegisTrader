"""Additional tests for config_validator CLI to improve coverage."""

import os
from unittest.mock import MagicMock, patch

import pytest

from aegis_sdk_dev.cli.config_validator import ConfigValidator, ValidationIssue, ValidationResult


class TestConfigValidatorPrivateMethods:
    """Test private methods of ConfigValidator."""

    def setup_method(self):
        """Setup test fixtures."""
        self.validator = ConfigValidator()
        self.validator.console = MagicMock()

    def test_detect_environment_kubernetes(self):
        """Test detecting Kubernetes environment."""
        # Arrange & Act
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True  # /var/run/secrets/kubernetes.io exists
            env = self.validator._detect_environment()

        # Assert
        assert env == "kubernetes"

    def test_detect_environment_docker(self):
        """Test detecting Docker environment."""
        # Arrange & Act
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = [False, True]  # Not k8s, but /.dockerenv exists
            env = self.validator._detect_environment()

        # Assert
        assert env == "docker"

    def test_detect_environment_k8s_env_vars(self):
        """Test detecting Kubernetes via environment variables."""
        # Arrange & Act
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False  # No k8s files
            with patch.dict(os.environ, {"KUBERNETES_SERVICE_HOST": "localhost"}):
                env = self.validator._detect_environment()

        # Assert
        assert env == "kubernetes"

    def test_detect_environment_local(self):
        """Test detecting local environment."""
        # Arrange & Act
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False  # No special files
            with patch.dict(os.environ, {}, clear=True):
                env = self.validator._detect_environment()

        # Assert
        assert env == "local"

    def test_validate_service_name_empty(self):
        """Test validating empty service name."""
        # Arrange
        result = ValidationResult(environment="local")

        # Act
        self.validator._validate_service_name("", result)

        # Assert
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].level == "ERROR"
        assert "empty" in result.issues[0].message.lower()

    def test_validate_service_name_too_short(self):
        """Test validating too short service name."""
        # Arrange
        result = ValidationResult(environment="local")

        # Act
        self.validator._validate_service_name("ab", result)

        # Assert
        assert not result.is_valid
        errors = result.get_issues_by_level("ERROR")
        assert len(errors) == 1
        assert "too short" in errors[0].message

    def test_validate_service_name_special_chars(self):
        """Test validating service name with special characters."""
        # Arrange
        result = ValidationResult(environment="local")

        # Act
        self.validator._validate_service_name("test@service!", result)

        # Assert
        warnings = result.get_issues_by_level("WARNING")
        assert len(warnings) == 1
        assert "special characters" in warnings[0].message

    def test_validate_service_name_uppercase(self):
        """Test validating service name with uppercase letters."""
        # Arrange
        result = ValidationResult(environment="local")

        # Act
        self.validator._validate_service_name("TestService", result)

        # Assert
        info = result.get_issues_by_level("INFO")
        assert len(info) == 1
        assert "uppercase" in info[0].message.lower()

    @patch("pathlib.Path.is_absolute")
    @patch("pathlib.Path.exists")
    def test_check_project_structure_missing_dirs(self, mock_exists, mock_is_absolute):
        """Test checking project structure with missing directories."""
        # Arrange
        result = ValidationResult(environment="local")
        mock_is_absolute.return_value = False
        mock_exists.return_value = False  # Project doesn't exist

        # Act
        self.validator._check_project_structure("test-service", result)

        # Assert
        errors = result.get_issues_by_level("ERROR")
        assert any("does not exist" in issue.message for issue in errors)

    @patch("pathlib.Path.is_absolute")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    @patch("os.listdir")
    def test_check_project_structure_existing_project(
        self, mock_listdir, mock_is_dir, mock_exists, mock_is_absolute
    ):
        """Test checking existing project structure."""
        # Arrange
        result = ValidationResult(environment="local")
        mock_is_absolute.return_value = False
        mock_exists.return_value = True
        mock_is_dir.return_value = True
        mock_listdir.return_value = ["domain", "application", "infrastructure", "tests"]

        # Act
        self.validator._check_project_structure("test-service", result)

        # Assert
        # Should add info about found directories
        info = result.get_issues_by_level("INFO")
        assert len(info) > 0

    @patch("subprocess.run")
    def test_check_docker_setup_docker_installed(self, mock_run):
        """Test checking Docker setup when Docker is installed."""
        # Arrange
        result = ValidationResult(environment="local")
        mock_run.return_value = MagicMock(returncode=0)

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False  # No Dockerfile

            # Act
            self.validator._check_docker_setup("test-service", result)

        # Assert
        assert result.diagnostics.get("docker_installed") is True
        info = result.get_issues_by_level("INFO")
        assert any("Missing Dockerfile" in issue.message for issue in info)

    @patch("subprocess.run")
    def test_check_docker_setup_docker_not_installed(self, mock_run):
        """Test checking Docker setup when Docker is not installed."""
        # Arrange
        result = ValidationResult(environment="local")
        mock_run.side_effect = FileNotFoundError()

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False

            # Act
            self.validator._check_docker_setup("test-service", result)

        # Assert
        warnings = result.get_issues_by_level("WARNING")
        assert any("Docker is not installed" in issue.message for issue in warnings)

    def test_check_kubernetes_setup(self):
        """Test checking Kubernetes setup."""
        # Arrange
        result = ValidationResult(environment="kubernetes")

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False  # No k8s manifests

            # Act
            self.validator._check_kubernetes_setup("test-service", result)

        # Assert
        warnings = result.get_issues_by_level("WARNING")
        assert any("k8s" in issue.message.lower() for issue in warnings)

    def test_generate_recommendations_with_errors(self):
        """Test generating recommendations when there are errors."""
        # Arrange
        result = ValidationResult(environment="local")
        result.add_issue(
            ValidationIssue(level="ERROR", category="NATS", message="Cannot connect to NATS")
        )

        # Act
        self.validator._generate_recommendations(result)

        # Assert
        assert len(result.recommendations) > 0
        assert any("Fix" in rec for rec in result.recommendations)

    def test_generate_recommendations_k8s_localhost(self):
        """Test generating recommendations for k8s with localhost."""
        # Arrange
        result = ValidationResult(environment="kubernetes")
        result.add_issue(
            ValidationIssue(
                level="ERROR",
                category="NATS",
                message="Cannot connect to NATS at nats://localhost:4222",
            )
        )

        # Act
        self.validator._generate_recommendations(result)

        # Assert
        assert any("Kubernetes" in rec and "DNS" in rec for rec in result.recommendations)


class TestConfigValidatorIntegration:
    """Integration tests for ConfigValidator."""

    @pytest.mark.asyncio
    async def test_validate_all_complete_flow(self):
        """Test complete validation flow."""
        # Arrange
        validator = ConfigValidator()
        validator.console = MagicMock()

        with (
            patch.object(validator, "_detect_environment", return_value="local"),
            patch.object(validator, "_validate_service_name"),
            patch.object(validator, "_check_project_structure"),
            patch.object(validator, "_validate_config_files"),
            patch.object(validator, "_check_nats_connection"),
            patch.object(validator, "_check_docker_setup"),
            patch.object(validator, "_generate_recommendations"),
        ):
            # Act
            result = await validator.validate_all("test-service", "nats://localhost:4222")

        # Assert
        assert isinstance(result, ValidationResult)
        assert result.environment == "local"

    @pytest.mark.asyncio
    async def test_validate_all_kubernetes_env(self):
        """Test validation in Kubernetes environment."""
        # Arrange
        validator = ConfigValidator()
        validator.console = MagicMock()

        with (
            patch.object(validator, "_detect_environment", return_value="kubernetes"),
            patch.object(validator, "_validate_service_name"),
            patch.object(validator, "_check_project_structure"),
            patch.object(validator, "_validate_config_files"),
            patch.object(validator, "_check_nats_connection"),
            patch.object(validator, "_check_docker_setup"),
            patch.object(validator, "_check_kubernetes_setup"),
            patch.object(validator, "_generate_recommendations"),
        ):
            # Act
            result = await validator.validate_all("test-service", environment="kubernetes")

        # Assert
        assert result.environment == "kubernetes"


class TestValidationHelpers:
    """Test validation helper functions."""

    def test_validation_issue_category_uppercase(self):
        """Test that ValidationIssue category is always uppercase."""
        # Arrange & Act
        issue = ValidationIssue(
            level="ERROR",
            category="nats",  # lowercase
            message="Test message",
        )

        # Assert
        assert issue.category == "NATS"

    def test_validation_result_add_issue_error(self):
        """Test adding error issue sets is_valid to False."""
        # Arrange
        result = ValidationResult(environment="local")
        assert result.is_valid is True

        # Act
        result.add_issue(ValidationIssue(level="ERROR", category="TEST", message="Test error"))

        # Assert
        assert result.is_valid is False

    def test_validation_result_add_issue_warning(self):
        """Test adding warning issue doesn't affect is_valid."""
        # Arrange
        result = ValidationResult(environment="local")

        # Act
        result.add_issue(ValidationIssue(level="WARNING", category="TEST", message="Test warning"))

        # Assert
        assert result.is_valid is True
