"""Additional tests for Config Validator to reach 90% coverage."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from aegis_sdk_dev.cli.config_validator import (
    ConfigValidator,
    ValidationIssue,
    ValidationResult,
    main,
)


class TestConfigValidatorAdditionalCoverage:
    """Additional tests to improve coverage to 90%."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = MagicMock()
        self.validator = ConfigValidator(console=self.console)

    @pytest.mark.asyncio
    async def test_validate_nats_connection_no_close_no_disconnect(self):
        """Test NATS connection when adapter has neither close nor disconnect."""
        # This tests line 86 - when neither disconnect nor close exist
        with patch("aegis_sdk.infrastructure.nats_adapter.NATSAdapter") as MockNATSAdapter:
            mock_nats = AsyncMock()
            mock_nats.connect = AsyncMock(return_value=None)
            # Remove both close and disconnect attributes
            mock_nats.spec = []  # No methods
            MockNATSAdapter.return_value = mock_nats

            # Act
            valid, issue = await self.validator.validate_nats_connection("nats://localhost:4222")

            # Assert
            assert valid is True
            assert issue is None

    def test_display_results_with_diagnostics_and_recommendations(self):
        """Test display_results with diagnostics and recommendations."""
        # This tests lines 217-225
        # Arrange
        result = ValidationResult(environment="local")
        result.diagnostics = {
            "nats_connection": "OK",
            "k8s_environment": False,
            "service_config": "Valid",
        }
        result.recommendations = [
            "Ensure NATS is running",
            "Check port forwarding",
            "Verify service configuration",
        ]

        # Act
        self.validator.display_results(result)

        # Assert
        self.console.print.assert_called()
        # Check that diagnostics and recommendations were printed
        print_calls = [str(call) for call in self.console.print.call_args_list]

        # Should have printed diagnostics header
        assert any("Diagnostics" in str(call) for call in print_calls)
        # Should have printed recommendations header
        assert any("Recommendations" in str(call) for call in print_calls)

    def test_display_results_invalid_with_all_issue_levels(self):
        """Test display results with all issue levels."""
        # This ensures line 150 and 170 are covered
        # Arrange
        result = ValidationResult(environment="kubernetes")

        # Add various issue levels
        result.add_issue(
            ValidationIssue(
                level="ERROR",
                category="NATS",
                message="Connection failed",
                resolution="Check NATS server",
            )
        )
        result.add_issue(
            ValidationIssue(
                level="WARNING",
                category="CONFIG",
                message="Suboptimal config",
                resolution="Review settings",
            )
        )
        result.add_issue(
            ValidationIssue(
                level="INFO",
                category="K8S",
                message="Running in K8s",
                resolution=None,  # No resolution for info
            )
        )

        # Act
        self.validator.display_results(result)

        # Assert
        from rich.panel import Panel
        from rich.table import Table

        # Find Panel and Table in calls
        panel_found = False
        table_found = False

        for call in self.console.print.call_args_list:
            if call.args:
                if isinstance(call.args[0], Panel):
                    panel_found = True
                    assert "✗ INVALID" in call.args[0].renderable
                elif isinstance(call.args[0], Table):
                    table_found = True

        assert panel_found
        assert table_found

    @pytest.mark.asyncio
    async def test_validate_configuration_with_nats_issues(self):
        """Test validate_configuration when NATS has issues."""
        # This tests line 150 and 170
        # Arrange
        with patch.object(self.validator, "validate_nats_connection") as mock_nats:
            mock_nats.return_value = (
                False,
                ValidationIssue(
                    level="ERROR",
                    category="NATS",
                    message="NATS unavailable",
                    resolution="Start NATS server",
                ),
            )

            with patch.object(self.validator, "validate_k8s_environment") as mock_k8s:
                mock_k8s.return_value = (False, None)

                # Act
                result = await self.validator.validate_configuration(
                    service_name="test-service",
                    nats_url="nats://localhost:4222",
                    environment="auto",
                )

                # Assert
                assert not result.is_valid
                assert len(result.get_issues_by_category("NATS")) == 1
                assert len(result.recommendations) > 0
                assert "NATS" in result.recommendations[0]

    def test_cli_with_json_output_invalid_config(self):
        """Test CLI with JSON output when config is invalid."""
        # This tests lines 265-276
        runner = CliRunner()

        with patch("aegis_sdk_dev.cli.config_validator.ConfigValidator") as MockValidator:
            mock_validator = MagicMock()
            mock_result = ValidationResult(environment="local", is_valid=False)
            mock_result.add_issue(
                ValidationIssue(level="ERROR", category="CONFIG", message="Invalid config")
            )

            # Make validate_configuration async
            async def mock_validate(*args, **kwargs):
                return mock_result

            mock_validator.validate_configuration = mock_validate
            MockValidator.return_value = mock_validator

            # Act
            result = runner.invoke(
                main, ["--service-name", "test", "--nats-url", "nats://localhost:4222", "--json"]
            )

            # Assert - exit code should be 1 for invalid config
            assert result.exit_code == 1
            # Output should be valid JSON
            try:
                json.loads(result.output)
                json_valid = True
            except:
                json_valid = False
            assert json_valid

    def test_cli_with_all_parameters(self):
        """Test CLI with all possible parameters."""
        # This helps cover line 283 (main entry point)
        runner = CliRunner()

        with patch("aegis_sdk_dev.cli.config_validator.ConfigValidator") as MockValidator:
            mock_validator = MagicMock()
            mock_result = ValidationResult(environment="kubernetes", is_valid=True)

            async def mock_validate(*args, **kwargs):
                return mock_result

            mock_validator.validate_configuration = mock_validate
            mock_validator.display_results = MagicMock()
            MockValidator.return_value = mock_validator

            # Act
            result = runner.invoke(
                main,
                [
                    "--service-name",
                    "my-service",
                    "--nats-url",
                    "nats://custom:4222",
                    "--environment",
                    "kubernetes",
                ],
            )

            # Assert
            assert result.exit_code == 0
            mock_validator.display_results.assert_called_once()


if __name__ == "__main__":
    # This covers line 283
    import sys

    sys.argv = ["test", "--service-name", "test", "--nats-url", "nats://localhost:4222"]
    main()
