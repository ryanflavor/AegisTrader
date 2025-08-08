"""Unit tests for Config Validator CLI following TDD principles."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from aegis_sdk_dev.cli.config_validator import (
    ConfigValidator,
    ValidationIssue,
    ValidationResult,
    main,
)


class TestValidationIssue:
    """Test ValidationIssue value object."""

    def test_create_valid_issue(self):
        """Test creating a valid validation issue."""
        # Arrange & Act
        issue = ValidationIssue(
            level="ERROR",
            category="NATS",
            message="Connection failed",
            resolution="Check NATS server",
        )

        # Assert
        assert issue.level == "ERROR"
        assert issue.category == "NATS"
        assert issue.message == "Connection failed"
        assert issue.resolution == "Check NATS server"
        assert issue.details == {}

    def test_invalid_level_raises_error(self):
        """Test that invalid level raises validation error."""
        # Act & Assert
        with pytest.raises(ValueError, match="Level must be one of"):
            ValidationIssue(level="INVALID", category="TEST", message="Test message")

    def test_issue_with_details(self):
        """Test creating issue with additional details."""
        # Arrange & Act
        issue = ValidationIssue(
            level="WARNING",
            category="K8S",
            message="Not in K8s",
            details={"environment": "local", "port": 4222},
        )

        # Assert
        assert issue.details["environment"] == "local"
        assert issue.details["port"] == 4222


class TestValidationResult:
    """Test ValidationResult aggregate."""

    def test_create_valid_result(self):
        """Test creating a validation result."""
        # Arrange & Act
        result = ValidationResult(environment="local")

        # Assert
        assert result.is_valid is True
        assert result.environment == "local"
        assert result.issues == []
        assert result.diagnostics == {}
        assert result.recommendations == []

    def test_add_error_issue_invalidates_result(self):
        """Test that adding an error issue invalidates the result."""
        # Arrange
        result = ValidationResult(environment="local")
        issue = ValidationIssue(level="ERROR", category="NATS", message="Connection failed")

        # Act
        result.add_issue(issue)

        # Assert
        assert result.is_valid is False
        assert len(result.issues) == 1
        assert result.issues[0] == issue

    def test_add_warning_issue_keeps_valid(self):
        """Test that adding a warning doesn't invalidate the result."""
        # Arrange
        result = ValidationResult(environment="local")
        issue = ValidationIssue(
            level="WARNING", category="CONFIG", message="Suboptimal configuration"
        )

        # Act
        result.add_issue(issue)

        # Assert
        assert result.is_valid is True
        assert len(result.issues) == 1

    def test_get_issues_by_level(self):
        """Test filtering issues by level."""
        # Arrange
        result = ValidationResult(environment="local")
        error = ValidationIssue(level="ERROR", category="NATS", message="Error")
        warning = ValidationIssue(level="WARNING", category="CONFIG", message="Warning")
        info = ValidationIssue(level="INFO", category="K8S", message="Info")

        # Act
        result.add_issue(error)
        result.add_issue(warning)
        result.add_issue(info)

        # Assert
        assert len(result.get_issues_by_level("ERROR")) == 1
        assert len(result.get_issues_by_level("WARNING")) == 1
        assert len(result.get_issues_by_level("INFO")) == 1
        assert result.get_issues_by_level("ERROR")[0] == error

    def test_get_issues_by_category(self):
        """Test filtering issues by category."""
        # Arrange
        result = ValidationResult(environment="local")
        nats1 = ValidationIssue(level="ERROR", category="NATS", message="Error 1")
        nats2 = ValidationIssue(level="WARNING", category="NATS", message="Warning 1")
        config = ValidationIssue(level="INFO", category="CONFIG", message="Info")

        # Act
        result.add_issue(nats1)
        result.add_issue(nats2)
        result.add_issue(config)

        # Assert
        nats_issues = result.get_issues_by_category("NATS")
        assert len(nats_issues) == 2
        assert nats1 in nats_issues
        assert nats2 in nats_issues


class TestConfigValidator:
    """Test ConfigValidator application service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = MagicMock(spec=Console)
        self.validator = ConfigValidator(console=self.console)

    @pytest.mark.asyncio
    async def test_validate_nats_connection_success(self):
        """Test successful NATS connection validation."""
        # Arrange
        with patch("aegis_sdk.infrastructure.nats_adapter.NATSAdapter") as MockNATSAdapter:
            mock_nats = AsyncMock()
            mock_nats.connect = AsyncMock(return_value=None)
            mock_nats.disconnect = AsyncMock(return_value=None)
            MockNATSAdapter.return_value = mock_nats

            # Act
            valid, issue = await self.validator.validate_nats_connection("nats://localhost:4222")

            # Assert
            assert valid is True
            assert issue is None
            mock_nats.connect.assert_called_once()
            mock_nats.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_nats_connection_with_close_method(self):
        """Test successful NATS connection validation with close method fallback."""
        # Arrange - test close method fallback (lines 84-85)
        with patch("aegis_sdk.infrastructure.nats_adapter.NATSAdapter") as MockNATSAdapter:
            mock_nats = AsyncMock()
            mock_nats.connect = AsyncMock(return_value=None)
            # No disconnect method, only close
            mock_nats.close = AsyncMock(return_value=None)
            MockNATSAdapter.return_value = mock_nats

            # Act
            valid, issue = await self.validator.validate_nats_connection("nats://localhost:4222")

            # Assert
            assert valid is True
            assert issue is None
            mock_nats.connect.assert_called_once()
            mock_nats.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_nats_connection_timeout(self):
        """Test NATS connection validation with timeout."""
        # Arrange
        with patch("aegis_sdk_dev.cli.config_validator.asyncio.wait_for") as mock_wait_for:
            mock_wait_for.side_effect = asyncio.TimeoutError()

            # Act
            valid, issue = await self.validator.validate_nats_connection(
                "nats://localhost:4222", timeout=1
            )

            # Assert
            assert valid is False
            assert issue is not None
            assert issue.level == "ERROR"
            assert issue.category == "NATS"
            assert "timed out" in issue.message

    @pytest.mark.asyncio
    async def test_validate_nats_connection_error(self):
        """Test NATS connection validation with error."""
        # Arrange
        with patch("aegis_sdk_dev.cli.config_validator.asyncio.wait_for") as mock_wait_for:
            mock_wait_for.side_effect = Exception("Connection refused")

            # Act
            valid, issue = await self.validator.validate_nats_connection("nats://localhost:4222")

            # Assert
            assert valid is False
            assert issue is not None
            assert issue.level == "ERROR"
            assert issue.category == "NATS"
            assert "Failed to connect" in issue.message

    @pytest.mark.asyncio
    async def test_validate_k8s_environment_true(self):
        """Test K8s environment validation when in K8s."""
        # Arrange
        with patch("os.path.exists", return_value=True):
            # Act
            valid, issue = await self.validator.validate_k8s_environment()

            # Assert
            assert valid is True
            assert issue is None

    @pytest.mark.asyncio
    async def test_validate_k8s_environment_false(self):
        """Test K8s environment validation when not in K8s."""
        # Arrange
        with patch("os.path.exists", return_value=False):
            with patch("os.getenv", return_value=None):
                # Act
                valid, issue = await self.validator.validate_k8s_environment()

                # Assert
                assert valid is False
                assert issue is not None
                assert issue.level == "INFO"
                assert issue.category == "K8S"

    @pytest.mark.asyncio
    async def test_validate_configuration_complete(self):
        """Test complete configuration validation."""
        # Arrange
        with patch.object(self.validator, "validate_nats_connection") as mock_nats:
            with patch.object(self.validator, "validate_k8s_environment") as mock_k8s:
                mock_nats.return_value = (True, None)
                mock_k8s.return_value = (
                    False,
                    ValidationIssue(level="INFO", category="K8S", message="Not in K8s"),
                )

                # Act
                result = await self.validator.validate_configuration(
                    service_name="test-service", nats_url="nats://localhost:4222"
                )

                # Assert
                assert result.is_valid is True
                assert result.environment == "local"
                assert len(result.issues) == 1
                assert result.diagnostics["nats_connection"] == "OK"

    @pytest.mark.asyncio
    async def test_validate_configuration_invalid_service_name(self):
        """Test configuration validation with invalid service name."""
        # Arrange
        with patch.object(self.validator, "validate_nats_connection") as mock_nats:
            with patch.object(self.validator, "validate_k8s_environment") as mock_k8s:
                mock_nats.return_value = (True, None)
                mock_k8s.return_value = (True, None)

                # Act
                result = await self.validator.validate_configuration(
                    service_name="ab",  # Too short
                    nats_url="nats://localhost:4222",
                )

                # Assert
                assert result.is_valid is False
                assert len(result.get_issues_by_category("CONFIG")) == 1

    def test_display_results_valid(self):
        """Test displaying valid results."""
        # Arrange
        result = ValidationResult(environment="local", is_valid=True)

        # Act
        self.validator.display_results(result)

        # Assert
        self.console.print.assert_called()
        # Check that Panel was created with success status
        from rich.panel import Panel

        calls = self.console.print.call_args_list
        # Find the Panel call
        panel_call = None
        for call in calls:
            if call.args and isinstance(call.args[0], Panel):
                panel_call = call.args[0]
                break
        assert panel_call is not None
        assert "✓ VALID" in panel_call.renderable

    def test_display_results_with_issues(self):
        """Test displaying results with issues."""
        # Arrange
        result = ValidationResult(environment="local")
        result.add_issue(
            ValidationIssue(
                level="ERROR",
                category="NATS",
                message="Connection failed",
                resolution="Check NATS",
            )
        )

        # Act
        self.validator.display_results(result)

        # Assert
        self.console.print.assert_called()
        # Check that error was displayed
        from rich.panel import Panel
        from rich.table import Table

        calls = self.console.print.call_args_list
        # Find the Panel call
        panel_found = False
        table_found = False
        for call in calls:
            if call.args:
                if isinstance(call.args[0], Panel):
                    panel_found = True
                    assert "✗ INVALID" in call.args[0].renderable
                elif isinstance(call.args[0], Table):
                    table_found = True
        assert panel_found
        assert table_found


class TestConfigValidatorCLI:
    """Test Config Validator CLI interface."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_help(self):
        """Test CLI help output."""
        # Act
        result = self.runner.invoke(main, ["--help"])

        # Assert
        assert result.exit_code == 0
        assert "Validate AegisSDK configuration" in result.output
        assert "--service-name" in result.output
        assert "--nats-url" in result.output
        assert "--environment" in result.output
        assert "--json" in result.output

    @patch("aegis_sdk_dev.cli.config_validator.asyncio.run")
    def test_cli_with_service_name(self, mock_run):
        """Test CLI with service name parameter."""
        # Arrange
        mock_run.return_value = 0

        # Act
        result = self.runner.invoke(main, ["--service-name", "test-service"])

        # Assert
        assert result.exit_code == 0
        mock_run.assert_called_once()

    @patch("aegis_sdk_dev.cli.config_validator.asyncio.run")
    def test_cli_with_json_output(self, mock_run):
        """Test CLI with JSON output flag."""
        # Arrange
        mock_result = ValidationResult(environment="local")
        mock_run.return_value = 0

        # Act
        result = self.runner.invoke(main, ["--service-name", "test-service", "--json"])

        # Assert
        assert result.exit_code == 0
        mock_run.assert_called_once()

    def test_cli_missing_required_param(self):
        """Test CLI with missing required parameter."""
        # Act
        result = self.runner.invoke(main, [])

        # Assert
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    @patch("aegis_sdk_dev.cli.config_validator.asyncio.run")
    def test_cli_all_parameters(self, mock_run):
        """Test CLI with all parameters."""
        # Arrange
        mock_run.return_value = 0

        # Act
        result = self.runner.invoke(
            main,
            [
                "--service-name",
                "test-service",
                "--nats-url",
                "nats://custom:4222",
                "--environment",
                "kubernetes",
                "--json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_run.assert_called_once()
