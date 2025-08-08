"""Comprehensive unit tests for ValidationService to improve coverage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis_sdk_dev.application.validation_service import ValidationService
from aegis_sdk_dev.domain.models import (
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)


class TestValidationServiceComprehensive:
    """Comprehensive test suite for ValidationService."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        # Create mock ports (infrastructure adapters)
        self.mock_console = MagicMock()
        self.mock_environment = MagicMock()
        self.mock_nats = MagicMock()

        # Create service under test
        self.service = ValidationService(
            console=self.mock_console,
            environment=self.mock_environment,
            nats=self.mock_nats,
        )

    @pytest.mark.asyncio
    async def test_validate_service_configuration_all_valid(self):
        """Test validation when everything is valid."""
        # Arrange
        self.mock_nats.connect = AsyncMock(return_value=True)
        self.mock_nats.disconnect = AsyncMock()
        self.mock_environment.is_kubernetes_environment.return_value = True
        self.mock_environment.detect_environment.return_value = "kubernetes"

        # Act
        result = await self.service.validate_service_configuration(
            service_name="valid-service",
            nats_url="nats://localhost:4222",
            environment="auto",
        )

        # Assert
        assert result.is_valid is True
        assert result.diagnostics["nats_connection"] == "OK"
        assert result.diagnostics["detected_environment"] == "kubernetes"
        assert result.environment == "kubernetes"

        # Verify NATS was properly connected and disconnected
        self.mock_nats.connect.assert_called_once_with("nats://localhost:4222", 5.0)
        self.mock_nats.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_service_configuration_nats_connection_error(self):
        """Test validation when NATS connection fails with ConnectionError."""
        # Arrange
        self.mock_nats.connect = AsyncMock(side_effect=ConnectionError("Connection refused"))
        self.mock_environment.is_kubernetes_environment.return_value = False
        self.mock_environment.detect_environment.return_value = "local"

        # Act
        result = await self.service.validate_service_configuration(
            service_name="test-service",
            nats_url="nats://bad-host:4222",
            environment="auto",
        )

        # Assert
        assert result.is_valid is False
        nats_issues = result.get_issues_by_category("NATS")
        assert len(nats_issues) > 0
        assert nats_issues[0].level == ValidationLevel.ERROR
        assert "Connection refused" in nats_issues[0].message
        assert "kubectl port-forward" in nats_issues[0].resolution

    @pytest.mark.asyncio
    async def test_validate_service_configuration_nats_generic_exception(self):
        """Test validation when NATS connection fails with generic exception."""
        # Arrange
        self.mock_nats.connect = AsyncMock(side_effect=Exception("Unknown error"))
        self.mock_environment.is_kubernetes_environment.return_value = True

        # Act
        result = await self.service.validate_service_configuration(
            service_name="test-service",
            nats_url="nats://localhost:4222",
            environment="production",
        )

        # Assert
        assert result.is_valid is False
        nats_issues = result.get_issues_by_category("NATS")
        assert len(nats_issues) > 0
        assert nats_issues[0].level == ValidationLevel.ERROR
        assert "Unknown error" in nats_issues[0].message

    @pytest.mark.asyncio
    async def test_validate_service_configuration_nats_returns_false(self):
        """Test validation when NATS connect returns False."""
        # Arrange
        self.mock_nats.connect = AsyncMock(return_value=False)
        self.mock_environment.is_kubernetes_environment.return_value = False
        self.mock_environment.detect_environment.return_value = "local"

        # Act
        result = await self.service.validate_service_configuration(
            service_name="test-service",
            nats_url="nats://localhost:4222",
        )

        # Assert
        assert result.is_valid is False
        nats_issues = result.get_issues_by_category("NATS")
        assert len(nats_issues) > 0
        assert "Unable to connect to NATS" in nats_issues[0].message

    @pytest.mark.asyncio
    async def test_validate_service_configuration_not_in_kubernetes(self):
        """Test validation in non-Kubernetes environment."""
        # Arrange
        self.mock_nats.connect = AsyncMock(return_value=True)
        self.mock_nats.disconnect = AsyncMock()
        self.mock_environment.is_kubernetes_environment.return_value = False
        self.mock_environment.detect_environment.return_value = "local"

        # Act
        result = await self.service.validate_service_configuration(
            service_name="local-service",
            nats_url="nats://localhost:4222",
            environment="auto",
        )

        # Assert
        # Should have INFO level issue about not being in K8s
        env_issues = result.get_issues_by_category("ENVIRONMENT")
        assert len(env_issues) > 0
        assert env_issues[0].level == ValidationLevel.INFO
        assert "Not running in Kubernetes" in env_issues[0].message
        assert "port-forwarding" in env_issues[0].resolution

    @pytest.mark.asyncio
    async def test_validate_nats_connection_with_custom_timeout(self):
        """Test NATS validation with custom timeout."""
        # Arrange
        self.mock_nats.connect = AsyncMock(return_value=True)
        self.mock_nats.disconnect = AsyncMock()

        # Act
        issue = await self.service._validate_nats_connection("nats://test:4222", timeout=10.0)

        # Assert
        assert issue is None
        self.mock_nats.connect.assert_called_once_with("nats://test:4222", 10.0)

    def test_validate_environment_in_kubernetes(self):
        """Test environment validation when running in Kubernetes."""
        # Arrange
        self.mock_environment.is_kubernetes_environment.return_value = True

        # Act
        issue = self.service._validate_environment()

        # Assert
        assert issue is None

    def test_validate_environment_not_in_kubernetes(self):
        """Test environment validation when not in Kubernetes."""
        # Arrange
        self.mock_environment.is_kubernetes_environment.return_value = False
        self.mock_environment.detect_environment.return_value = "docker"

        # Act
        issue = self.service._validate_environment()

        # Assert
        assert issue is not None
        assert issue.level == ValidationLevel.INFO
        assert issue.category == "ENVIRONMENT"
        assert "Not running in Kubernetes" in issue.message
        assert issue.details["k8s_detected"] is False
        assert issue.details["environment"] == "docker"

    def test_add_environment_recommendations_nats_issues_kubernetes(self):
        """Test adding recommendations for NATS issues in Kubernetes."""
        # Arrange
        result = ValidationResult()
        result.environment = "kubernetes"
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                category="NATS",
                message="Connection failed",
            )
        )

        # Act
        self.service._add_environment_recommendations(result)

        # Assert
        assert len(result.recommendations) > 0
        assert any("namespace" in rec for rec in result.recommendations)

    def test_add_environment_recommendations_nats_issues_local(self):
        """Test adding recommendations for NATS issues in local environment."""
        # Arrange
        result = ValidationResult()
        result.environment = "local"
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                category="NATS",
                message="Connection failed",
            )
        )

        # Act
        self.service._add_environment_recommendations(result)

        # Assert
        assert len(result.recommendations) > 0
        assert any("kubectl port-forward" in rec for rec in result.recommendations)

    def test_add_environment_recommendations_localhost_in_kubernetes(self):
        """Test recommendations when using localhost in Kubernetes."""
        # Arrange
        result = ValidationResult()
        result.environment = "kubernetes"
        result.diagnostics["nats_url"] = "nats://localhost:4222"
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.WARNING,
                category="NATS",
                message="Using localhost",
            )
        )

        # Act
        self.service._add_environment_recommendations(result)

        # Assert
        assert any("Kubernetes service DNS" in rec for rec in result.recommendations)

    def test_display_validation_results_valid(self):
        """Test display of validation results when valid."""
        # Arrange
        result = ValidationResult()
        result.environment = "production"
        result.diagnostics = {
            "nats_connection": "OK",
            "environment": "kubernetes",
        }
        result.recommendations = ["Use service mesh for better observability"]

        # Act
        self.service.display_validation_results(result)

        # Assert
        # Verify panel display with success
        self.mock_console.print_panel.assert_called_once()
        panel_args = self.mock_console.print_panel.call_args
        assert "✓ VALID" in panel_args[0][0]
        assert panel_args[1]["style"] == "green"

        # Verify diagnostics displayed
        self.mock_console.print.assert_any_call("\n[bold]Diagnostics:[/bold]")
        self.mock_console.print.assert_any_call("  • nats_connection: OK")

        # Verify recommendations displayed
        self.mock_console.print.assert_any_call("\n[bold yellow]Recommendations:[/bold yellow]")

    def test_display_validation_results_invalid_with_errors(self):
        """Test display of validation results with errors."""
        # Arrange
        result = ValidationResult()
        result.environment = "local"
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                category="CONFIG",
                message="Invalid service name",
                resolution="Use alphanumeric characters only",
            )
        )
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.WARNING,
                category="NATS",
                message="Using default port",
                resolution="Consider using custom port for production",
            )
        )

        # Act
        self.service.display_validation_results(result)

        # Assert
        # Verify panel shows invalid
        self.mock_console.print_panel.assert_called_once()
        panel_args = self.mock_console.print_panel.call_args
        assert "✗ INVALID" in panel_args[0][0]
        assert panel_args[1]["style"] == "red"

        # Verify table with issues
        self.mock_console.print_table.assert_called_once()
        table_args = self.mock_console.print_table.call_args
        headers = table_args[0][0]
        rows = table_args[0][1]

        assert headers == ["Level", "Category", "Message", "Resolution"]
        assert len(rows) == 2

        # Check error row
        assert "ERROR" in rows[0][0]
        assert rows[0][1] == "CONFIG"
        assert rows[0][2] == "Invalid service name"

        # Check warning row
        assert "WARNING" in rows[1][0]
        assert rows[1][1] == "NATS"

    def test_display_validation_results_info_only(self):
        """Test display with only INFO level issues."""
        # Arrange
        result = ValidationResult()
        result.environment = "development"
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.INFO,
                category="ENVIRONMENT",
                message="Running in development mode",
            )
        )

        # Act
        self.service.display_validation_results(result)

        # Assert
        # INFO issues alone shouldn't make validation invalid
        self.mock_console.print_table.assert_called_once()
        table_args = self.mock_console.print_table.call_args
        rows = table_args[0][1]
        assert "INFO" in rows[0][0]

    def test_display_validation_results_no_resolution(self):
        """Test display when issues have no resolution."""
        # Arrange
        result = ValidationResult()
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.WARNING,
                category="TEST",
                message="Test warning",
                resolution=None,  # No resolution provided
            )
        )

        # Act
        self.service.display_validation_results(result)

        # Assert
        self.mock_console.print_table.assert_called_once()
        table_args = self.mock_console.print_table.call_args
        rows = table_args[0][1]
        assert rows[0][3] == "N/A"  # Resolution should show N/A

    def test_display_validation_results_empty_diagnostics_and_recommendations(self):
        """Test display with no diagnostics or recommendations."""
        # Arrange
        result = ValidationResult()
        result.environment = "test"

        # Act
        self.service.display_validation_results(result)

        # Assert
        # Should only show panel, no diagnostics or recommendations sections
        self.mock_console.print_panel.assert_called_once()

        # Diagnostics header should not be printed
        calls = [str(call) for call in self.mock_console.print.call_args_list]
        assert not any("Diagnostics" in str(call) for call in calls)
        assert not any("Recommendations" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_validate_service_configuration_with_explicit_environment(self):
        """Test validation with explicitly set environment (not auto)."""
        # Arrange
        self.mock_nats.connect = AsyncMock(return_value=True)
        self.mock_nats.disconnect = AsyncMock()
        self.mock_environment.is_kubernetes_environment.return_value = False

        # Act
        result = await self.service.validate_service_configuration(
            service_name="prod-service",
            nats_url="nats://prod-nats:4222",
            environment="production",  # Explicit environment
        )

        # Assert
        # Should not detect environment when explicitly provided
        assert result.environment == "production"  # From ValidationResult default
        assert "detected_environment" not in result.diagnostics
        self.mock_environment.detect_environment.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_service_configuration_domain_validation_issues(self):
        """Test that domain validation issues are included in result."""
        # Arrange
        self.mock_nats.connect = AsyncMock(return_value=True)
        self.mock_nats.disconnect = AsyncMock()
        self.mock_environment.is_kubernetes_environment.return_value = True

        # Act
        result = await self.service.validate_service_configuration(
            service_name="",  # Invalid empty service name
            nats_url="invalid-url",  # Invalid URL format
            environment="auto",
        )

        # Assert
        # Should have validation issues from domain validator
        assert not result.is_valid
        config_issues = result.get_issues_by_category("CONFIG")
        assert len(config_issues) > 0

    def test_display_validation_results_with_all_issue_levels(self):
        """Test display with ERROR, WARNING, and INFO level issues."""
        # Arrange
        result = ValidationResult()
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                category="CRITICAL",
                message="Critical error",
                resolution="Fix immediately",
            )
        )
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.WARNING,
                category="WARN",
                message="Warning message",
                resolution="Consider fixing",
            )
        )
        result.add_issue(
            ValidationIssue(
                level=ValidationLevel.INFO,
                category="INFO",
                message="Information",
                resolution="FYI",
            )
        )

        # Act
        self.service.display_validation_results(result)

        # Assert
        self.mock_console.print_table.assert_called_once()
        table_args = self.mock_console.print_table.call_args
        rows = table_args[0][1]

        # Should have all three levels with proper styling
        assert len(rows) == 3
        assert "ERROR" in rows[0][0] and "red" in rows[0][0]
        assert "WARNING" in rows[1][0] and "yellow" in rows[1][0]
        assert "INFO" in rows[2][0] and "cyan" in rows[2][0]
