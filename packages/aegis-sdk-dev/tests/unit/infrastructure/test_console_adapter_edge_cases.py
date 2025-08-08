"""Comprehensive edge case tests for ConsoleAdapter following TDD and hexagonal architecture.

These tests verify the adapter's behavior at architectural boundaries, focusing on
edge cases and error conditions. Following hexagonal architecture, we test the
adapter's implementation of the ConsolePort interface.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from aegis_sdk_dev.infrastructure.factory import InfrastructureFactory
from aegis_sdk_dev.ports.console import ConsolePort


class TestConsoleAdapterEdgeCases:
    """Test ConsoleAdapter edge cases and error conditions.

    These tests follow the AAA (Arrange-Act-Assert) pattern and focus on
    testing behavior at the port boundary rather than implementation details.
    """

    def setup_method(self):
        """Set up test fixtures using factory pattern."""
        # Arrange: Create mock console and adapter through factory
        self.mock_console = Mock(spec=Console)
        self.adapter = InfrastructureFactory.create_console(console=self.mock_console)

        # Verify adapter implements the port interface
        assert isinstance(self.adapter, ConsolePort)

    # Test initialization edge cases
    def test_init_with_none_console_creates_default(self):
        """Test adapter creates default console when None provided."""
        # Arrange & Act: Use factory to create adapter with default console
        adapter = InfrastructureFactory.create_console(console=None)

        # Assert: Verify adapter is properly initialized
        assert adapter is not None
        assert isinstance(adapter, ConsolePort)
        # Note: We don't test internal _console attribute (implementation detail)

    def test_init_with_custom_console(self):
        """Test adapter uses provided console instance."""
        # Arrange
        custom_console = Mock(spec=Console)

        # Act: Create adapter through factory
        adapter = InfrastructureFactory.create_console(console=custom_console)

        # Test behavior to verify correct console is used
        adapter.print("test")

        # Assert: Verify the custom console was called
        custom_console.print.assert_called_once_with("test")

    # Test print method edge cases
    def test_print_with_empty_string(self):
        """Test printing empty string doesn't fail."""
        # Act
        self.adapter.print("")

        # Assert
        self.mock_console.print.assert_called_once_with("")

    def test_print_with_none_message_raises(self):
        """Test printing None raises TypeError.

        This validates input validation at the port boundary.
        """
        # Act & Assert: Verify type safety is enforced
        with pytest.raises(TypeError, match="cannot be None"):
            self.adapter.print(None)

    def test_print_with_very_long_message(self):
        """Test printing extremely long message."""
        # Arrange
        long_message = "x" * 10000

        # Act
        self.adapter.print(long_message)

        # Assert
        self.mock_console.print.assert_called_once_with(long_message)

    def test_print_with_special_characters(self):
        """Test printing message with special characters."""
        # Arrange
        special_message = "Hello\n\t\r\x00World!@#$%^&*()"

        # Act
        self.adapter.print(special_message)

        # Assert
        self.mock_console.print.assert_called_once_with(special_message)

    def test_print_with_unicode_characters(self):
        """Test printing message with unicode characters."""
        # Arrange
        unicode_message = "Hello 世界 🌍 مرحبا"

        # Act
        self.adapter.print(unicode_message)

        # Assert
        self.mock_console.print.assert_called_once_with(unicode_message)

    def test_print_with_invalid_style(self):
        """Test printing with invalid style markup."""
        # Arrange
        message = "test"
        invalid_style = "not-a-real-style"

        # Act
        self.adapter.print(message, style=invalid_style)

        # Assert
        self.mock_console.print.assert_called_once_with(
            f"[{invalid_style}]{message}[/{invalid_style}]"
        )

    def test_print_with_nested_styles(self):
        """Test printing with nested style tags."""
        # Arrange
        message = "[bold]already styled[/bold]"
        style = "red"

        # Act
        self.adapter.print(message, style=style)

        # Assert
        self.mock_console.print.assert_called_once_with(f"[{style}]{message}[/{style}]")

    # Test error message edge cases
    def test_print_error_with_empty_message(self):
        """Test error printing with empty message."""
        # Act
        self.adapter.print_error("")

        # Assert
        self.mock_console.print.assert_called_once_with("[red bold]Error:[/red bold] ")

    def test_print_error_with_exception_object(self):
        """Test error printing with exception as message."""
        # Arrange
        error = ValueError("Something went wrong")

        # Act
        self.adapter.print_error(str(error))

        # Assert
        self.mock_console.print.assert_called_once_with(
            "[red bold]Error:[/red bold] Something went wrong"
        )

    def test_print_error_when_console_raises(self):
        """Test error handling when console.print raises."""
        # Arrange
        self.mock_console.print.side_effect = Exception("Console error")

        # Act & Assert
        with pytest.raises(Exception, match="Console error"):
            self.adapter.print_error("test")

    # Test warning message edge cases
    def test_print_warning_with_multiline_message(self):
        """Test warning with multiline message."""
        # Arrange
        message = "Line 1\nLine 2\nLine 3"

        # Act
        self.adapter.print_warning(message)

        # Assert
        self.mock_console.print.assert_called_once_with(f"[yellow]Warning:[/yellow] {message}")

    # Test success message edge cases
    def test_print_success_with_formatted_message(self):
        """Test success with pre-formatted message."""
        # Arrange
        message = "[bold]Already bold[/bold] text"

        # Act
        self.adapter.print_success(message)

        # Assert
        self.mock_console.print.assert_called_once_with(f"[green]✓[/green] {message}")

    # Test table printing edge cases
    def test_print_table_with_empty_headers(self):
        """Test table printing with empty headers list."""
        # Act
        self.adapter.print_table([], [], title="Empty Table")

        # Assert
        self.mock_console.print.assert_called_once()

    def test_print_table_with_mismatched_columns(self):
        """Test table with rows having different column counts."""
        # Arrange
        headers = ["Col1", "Col2", "Col3"]
        rows = [
            ["A", "B"],  # Missing column
            ["C", "D", "E", "F"],  # Extra column
            ["G", "H", "I"],  # Correct columns
        ]

        # Act
        self.adapter.print_table(headers, rows)

        # Assert
        self.mock_console.print.assert_called_once()

    def test_print_table_with_none_values(self):
        """Test table with None values in cells.

        Verifies graceful handling of None values in table data.
        """
        # Arrange
        headers = ["Name", "Value"]
        rows = [["Item1", None], [None, "Value2"]]

        # Act: Should handle None gracefully by converting to empty strings
        self.adapter.print_table(headers, rows)

        # Assert: Verify print was called (no exception raised)
        self.mock_console.print.assert_called_once()

    def test_print_table_with_very_long_content(self):
        """Test table with very long content in cells."""
        # Arrange
        headers = ["Column"]
        rows = [["x" * 1000]]

        # Act
        self.adapter.print_table(headers, rows)

        # Assert
        self.mock_console.print.assert_called_once()

    def test_print_table_with_special_characters_in_title(self):
        """Test table with special characters in title."""
        # Arrange
        headers = ["Test"]
        rows = [["Data"]]
        title = "Table\nWith\tSpecial™Characters"

        # Act
        self.adapter.print_table(headers, rows, title=title)

        # Assert
        self.mock_console.print.assert_called_once()

    # Test panel printing edge cases
    def test_print_panel_with_empty_content(self):
        """Test panel with empty content."""
        # Act
        self.adapter.print_panel("", title="Empty Panel")

        # Assert
        self.mock_console.print.assert_called_once()

    def test_print_panel_with_none_content_raises(self):
        """Test panel with None content raises error.

        Validates type safety at the port boundary.
        """
        # Act & Assert: Verify input validation
        with pytest.raises(TypeError, match="cannot be None"):
            self.adapter.print_panel(None)

    def test_print_panel_with_invalid_style(self):
        """Test panel with invalid style."""
        # Arrange
        content = "Test content"
        style = "not-a-style"

        # Act
        self.adapter.print_panel(content, style=style)

        # Assert
        assert self.mock_console.print.call_count == 1
        call_args = self.mock_console.print.call_args
        assert call_args[1]["style"] == style

    def test_print_panel_with_multiline_content(self):
        """Test panel with multiline content."""
        # Arrange
        content = """Line 1
        Line 2
        Line 3"""

        # Act
        self.adapter.print_panel(content, title="Multiline")

        # Assert
        self.mock_console.print.assert_called_once()

    # Test prompt edge cases
    @patch("aegis_sdk_dev.infrastructure.console_adapter.Prompt")
    def test_prompt_with_empty_message(self, mock_prompt_class):
        """Test prompt with empty message."""
        # Arrange
        mock_prompt_class.ask.return_value = "user_input"

        # Act
        result = self.adapter.prompt("")

        # Assert
        mock_prompt_class.ask.assert_called_once_with("", default=None)
        assert result == "user_input"

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Prompt")
    def test_prompt_with_keyboard_interrupt(self, mock_prompt_class):
        """Test prompt handling keyboard interrupt."""
        # Arrange
        mock_prompt_class.ask.side_effect = KeyboardInterrupt()

        # Act & Assert
        with pytest.raises(KeyboardInterrupt):
            self.adapter.prompt("Enter value")

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Prompt")
    def test_prompt_with_eof_error(self, mock_prompt_class):
        """Test prompt handling EOF error."""
        # Arrange
        mock_prompt_class.ask.side_effect = EOFError()

        # Act & Assert
        with pytest.raises(EOFError):
            self.adapter.prompt("Enter value")

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Prompt")
    def test_prompt_with_default_empty_string(self, mock_prompt_class):
        """Test prompt with empty string as default."""
        # Arrange
        mock_prompt_class.ask.return_value = ""

        # Act
        result = self.adapter.prompt("Enter value", default="")

        # Assert
        mock_prompt_class.ask.assert_called_once_with("Enter value", default="")
        assert result == ""

    # Test confirm edge cases
    @patch("aegis_sdk_dev.infrastructure.console_adapter.Confirm")
    def test_confirm_with_keyboard_interrupt(self, mock_confirm_class):
        """Test confirm handling keyboard interrupt."""
        # Arrange
        mock_confirm_class.ask.side_effect = KeyboardInterrupt()

        # Act & Assert
        with pytest.raises(KeyboardInterrupt):
            self.adapter.confirm("Are you sure?")

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Confirm")
    def test_confirm_with_invalid_input(self, mock_confirm_class):
        """Test confirm with invalid user input."""
        # Arrange
        mock_confirm_class.ask.side_effect = ValueError("Invalid input")

        # Act & Assert
        with pytest.raises(ValueError):
            self.adapter.confirm("Continue?")

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Confirm")
    def test_confirm_with_default_true(self, mock_confirm_class):
        """Test confirm with default True value."""
        # Arrange
        mock_confirm_class.ask.return_value = True

        # Act
        result = self.adapter.confirm("Proceed?", default=True)

        # Assert
        mock_confirm_class.ask.assert_called_once_with("Proceed?", default=True)
        assert result is True

    # Test console print failure scenarios
    def test_multiple_operations_with_console_failure(self):
        """Test multiple operations when console fails intermittently."""
        # Arrange
        self.mock_console.print.side_effect = [None, Exception("Failed"), None]

        # Act
        self.adapter.print("First")  # Should succeed

        with pytest.raises(Exception, match="Failed"):
            self.adapter.print_error("Second")  # Should fail

        # Reset side effect for next call
        self.mock_console.print.side_effect = None
        self.adapter.print_success("Third")  # Should succeed

    def test_console_closed_state(self):
        """Test operations when console is in closed/invalid state.

        Tests error propagation from infrastructure layer.
        """
        # Arrange: Simulate infrastructure failure
        self.mock_console.print.side_effect = RuntimeError("Console is closed")

        # Act & Assert: Verify error is properly propagated
        with pytest.raises(RuntimeError, match="Console is closed"):
            self.adapter.print("Test")
