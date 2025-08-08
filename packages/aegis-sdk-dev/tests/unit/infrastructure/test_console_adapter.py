"""Unit tests for ConsoleAdapter following TDD principles."""

from unittest.mock import MagicMock, patch

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aegis_sdk_dev.infrastructure.console_adapter import ConsoleAdapter
from aegis_sdk_dev.ports.console import ConsolePort


class TestConsoleAdapter:
    """Test ConsoleAdapter implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_console = MagicMock(spec=Console)
        self.adapter = ConsoleAdapter(self.mock_console)

    def test_implements_console_port(self):
        """Test that ConsoleAdapter implements ConsolePort interface."""
        # Assert
        assert isinstance(self.adapter, ConsolePort)

    def test_initialization_with_default_console(self):
        """Test initialization without providing a console."""
        # Act
        adapter = ConsoleAdapter()

        # Assert
        assert adapter._console is not None
        assert isinstance(adapter._console, Console)

    def test_initialization_with_custom_console(self):
        """Test initialization with a custom console."""
        # Arrange
        custom_console = MagicMock(spec=Console)

        # Act
        adapter = ConsoleAdapter(custom_console)

        # Assert
        assert adapter._console == custom_console

    def test_print_without_style(self):
        """Test printing a message without style."""
        # Arrange
        message = "Test message"

        # Act
        self.adapter.print(message)

        # Assert
        self.mock_console.print.assert_called_once_with(message)

    def test_print_with_style(self):
        """Test printing a message with style."""
        # Arrange
        message = "Test message"
        style = "bold green"

        # Act
        self.adapter.print(message, style)

        # Assert
        self.mock_console.print.assert_called_once_with(f"[{style}]{message}[/{style}]")

    def test_print_error(self):
        """Test printing an error message."""
        # Arrange
        message = "Error occurred"

        # Act
        self.adapter.print_error(message)

        # Assert
        self.mock_console.print.assert_called_once_with(f"[red bold]Error:[/red bold] {message}")

    def test_print_warning(self):
        """Test printing a warning message."""
        # Arrange
        message = "Warning message"

        # Act
        self.adapter.print_warning(message)

        # Assert
        self.mock_console.print.assert_called_once_with(f"[yellow]Warning:[/yellow] {message}")

    def test_print_success(self):
        """Test printing a success message."""
        # Arrange
        message = "Operation successful"

        # Act
        self.adapter.print_success(message)

        # Assert
        self.mock_console.print.assert_called_once_with(f"[green]✓[/green] {message}")

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Table")
    def test_print_table_without_title(self, mock_table_class):
        """Test printing a table without title."""
        # Arrange
        headers = ["Name", "Value"]
        rows = [["key1", "value1"], ["key2", "value2"]]
        mock_table = MagicMock(spec=Table)
        mock_table_class.return_value = mock_table

        # Act
        self.adapter.print_table(headers, rows)

        # Assert
        mock_table_class.assert_called_once()
        assert mock_table.add_column.call_count == 2
        mock_table.add_column.assert_any_call("Name")
        mock_table.add_column.assert_any_call("Value")
        assert mock_table.add_row.call_count == 2
        mock_table.add_row.assert_any_call("key1", "value1")
        mock_table.add_row.assert_any_call("key2", "value2")
        self.mock_console.print.assert_called_once_with(mock_table)

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Table")
    def test_print_table_with_title(self, mock_table_class):
        """Test printing a table with title."""
        # Arrange
        headers = ["Name", "Value"]
        rows = [["key1", "value1"]]
        title = "Configuration"
        mock_table = MagicMock(spec=Table)
        mock_table_class.return_value = mock_table

        # Act
        self.adapter.print_table(headers, rows, title)

        # Assert
        mock_table_class.assert_called_once()
        # Verify title was passed
        call_kwargs = mock_table_class.call_args[1]
        assert call_kwargs["title"] == title

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Panel")
    def test_print_panel_without_style(self, mock_panel_class):
        """Test printing a panel without style."""
        # Arrange
        content = "Panel content"
        title = "Panel Title"
        mock_panel = MagicMock(spec=Panel)
        mock_panel_class.return_value = mock_panel

        # Act
        self.adapter.print_panel(content, title)

        # Assert
        mock_panel_class.assert_called_once()
        call_args = mock_panel_class.call_args[0]
        call_kwargs = mock_panel_class.call_args[1]
        assert call_args[0] == content
        assert call_kwargs["title"] == title
        self.mock_console.print.assert_called_once_with(mock_panel)

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Panel")
    def test_print_panel_with_style(self, mock_panel_class):
        """Test printing a panel with style."""
        # Arrange
        content = "Panel content"
        title = "Panel Title"
        style = "bold blue"
        mock_panel = MagicMock(spec=Panel)
        mock_panel_class.return_value = mock_panel

        # Act
        self.adapter.print_panel(content, title, style)

        # Assert
        self.mock_console.print.assert_called_once_with(mock_panel, style=style)

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Prompt")
    def test_prompt_without_default(self, mock_prompt_class):
        """Test prompting user for input without default."""
        # Arrange
        message = "Enter value"
        expected_value = "user_input"
        mock_prompt_class.ask.return_value = expected_value

        # Act
        result = self.adapter.prompt(message)

        # Assert
        mock_prompt_class.ask.assert_called_once_with(message, default=None)
        assert result == expected_value

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Prompt")
    def test_prompt_with_default(self, mock_prompt_class):
        """Test prompting user for input with default."""
        # Arrange
        message = "Enter value"
        default = "default_value"
        expected_value = "user_input"
        mock_prompt_class.ask.return_value = expected_value

        # Act
        result = self.adapter.prompt(message, default)

        # Assert
        mock_prompt_class.ask.assert_called_once_with(message, default=default)
        assert result == expected_value

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Confirm")
    def test_confirm_with_default_false(self, mock_confirm_class):
        """Test asking for confirmation with default False."""
        # Arrange
        message = "Continue?"
        mock_confirm_class.ask.return_value = True

        # Act
        result = self.adapter.confirm(message)

        # Assert
        mock_confirm_class.ask.assert_called_once_with(message, default=False)
        assert result is True

    @patch("aegis_sdk_dev.infrastructure.console_adapter.Confirm")
    def test_confirm_with_default_true(self, mock_confirm_class):
        """Test asking for confirmation with default True."""
        # Arrange
        message = "Continue?"
        default = True
        mock_confirm_class.ask.return_value = False

        # Act
        result = self.adapter.confirm(message, default)

        # Assert
        mock_confirm_class.ask.assert_called_once_with(message, default=True)
        assert result is False

    def test_console_adapter_stateless(self):
        """Test that ConsoleAdapter is stateless."""
        # Arrange
        adapter1 = ConsoleAdapter()
        adapter2 = ConsoleAdapter()

        # Assert
        assert adapter1 is not adapter2
        assert adapter1._console is not adapter2._console

    def test_console_adapter_thread_safety(self):
        """Test that ConsoleAdapter can be used from multiple threads."""
        # This test verifies the adapter doesn't maintain state that could cause issues
        # The adapter should be safe to use from multiple threads as it only delegates

        # Arrange
        import threading

        results = []

        def print_message(adapter, message):
            adapter.print(message)
            results.append(message)

        # Act
        threads = []
        for i in range(5):
            thread = threading.Thread(target=print_message, args=(self.adapter, f"Message {i}"))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Assert
        assert len(results) == 5
        assert self.mock_console.print.call_count == 5
