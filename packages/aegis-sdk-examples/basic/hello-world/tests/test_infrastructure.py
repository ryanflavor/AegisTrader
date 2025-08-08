"""Tests for infrastructure adapters."""

import pytest
from app.infrastructure.console_notification_adapter import ConsoleNotificationAdapter
from app.infrastructure.file_audit_adapter import FileAuditAdapter
from app.infrastructure.in_memory_metrics_adapter import InMemoryMetricsAdapter


class TestInMemoryMetricsAdapter:
    """Test InMemoryMetricsAdapter."""

    def test_increment(self):
        """Test incrementing a metric."""
        adapter = InMemoryMetricsAdapter()

        adapter.increment("test.metric")
        adapter.increment("test.metric")
        adapter.increment("other.metric")

        assert adapter.get_count("test.metric") == 2
        assert adapter.get_count("other.metric") == 1
        assert adapter.get_count("nonexistent") == 0

    def test_record_latency(self):
        """Test recording latency."""
        adapter = InMemoryMetricsAdapter()

        adapter.record_latency("api.request", 100.5)
        adapter.record_latency("api.request", 200.3)
        adapter.record_latency("db.query", 50.0)

        api_latencies = adapter.get_latencies("api.request")
        assert len(api_latencies) == 2
        assert 100.5 in api_latencies
        assert 200.3 in api_latencies

        db_latencies = adapter.get_latencies("db.query")
        assert len(db_latencies) == 1
        assert 50.0 in db_latencies

    def test_get_all_metrics(self):
        """Test getting all metrics."""
        adapter = InMemoryMetricsAdapter()

        adapter.increment("counter1")
        adapter.increment("counter2")
        adapter.record_latency("latency1", 10.0)

        all_metrics = adapter.get_all_metrics()

        assert "counters" in all_metrics
        assert "latencies" in all_metrics
        assert all_metrics["counters"]["counter1"] == 1
        assert all_metrics["counters"]["counter2"] == 1
        assert len(all_metrics["latencies"]["latency1"]) == 1

    def test_reset(self):
        """Test resetting metrics."""
        adapter = InMemoryMetricsAdapter()

        adapter.increment("test")
        adapter.record_latency("test", 100.0)

        adapter.reset()

        assert adapter.get_count("test") == 0
        assert adapter.get_latencies("test") == []
        assert adapter.get_all_metrics() == {"counters": {}, "latencies": {}}


class TestFileAuditAdapter:
    """Test FileAuditAdapter."""

    @pytest.fixture
    def temp_audit_file(self, tmp_path):
        """Create temporary audit file."""
        return tmp_path / "audit.log"

    @pytest.mark.asyncio
    async def test_log_greeting(self, temp_audit_file):
        """Test logging a greeting."""
        adapter = FileAuditAdapter(str(temp_audit_file))

        await adapter.log_greeting("Alice", "Hello, Alice!")

        # Check file was created and contains the log
        assert temp_audit_file.exists()
        content = temp_audit_file.read_text()
        assert "Alice" in content
        assert "Hello, Alice!" in content
        assert "GREETING" in content

    @pytest.mark.asyncio
    async def test_log_event(self, temp_audit_file):
        """Test logging a generic event."""
        adapter = FileAuditAdapter(str(temp_audit_file))

        await adapter.log_event("USER_LOGIN", {"user": "bob", "ip": "192.168.1.1"})

        content = temp_audit_file.read_text()
        assert "USER_LOGIN" in content
        assert "bob" in content
        assert "192.168.1.1" in content

    @pytest.mark.asyncio
    async def test_multiple_logs(self, temp_audit_file):
        """Test multiple log entries."""
        adapter = FileAuditAdapter(str(temp_audit_file))

        await adapter.log_greeting("User1", "Hi User1")
        await adapter.log_greeting("User2", "Hi User2")
        await adapter.log_event("TEST", {"data": "test"})

        content = temp_audit_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3  # Three log entries

    @pytest.mark.asyncio
    async def test_file_creation_error(self):
        """Test handling file creation errors."""
        # Use invalid path
        adapter = FileAuditAdapter("/invalid/path/audit.log")

        # Should not raise, just log error internally
        await adapter.log_greeting("Test", "Test message")


class TestConsoleNotificationAdapter:
    """Test ConsoleNotificationAdapter."""

    @pytest.mark.asyncio
    async def test_send_greeting_notification(self, capsys):
        """Test sending greeting notification to console."""
        adapter = ConsoleNotificationAdapter()

        await adapter.send_greeting_notification("Bob", "Hey Bob!")

        captured = capsys.readouterr()
        assert "📢 Greeting Notification" in captured.out
        assert "Bob" in captured.out
        assert "Hey Bob!" in captured.out

    @pytest.mark.asyncio
    async def test_send_notification(self, capsys):
        """Test sending generic notification."""
        adapter = ConsoleNotificationAdapter()

        await adapter.send_notification("Test Title", "Test message content", {"key": "value"})

        captured = capsys.readouterr()
        assert "Test Title" in captured.out
        assert "Test message content" in captured.out
        assert "key" in captured.out
        assert "value" in captured.out

    @pytest.mark.asyncio
    async def test_notification_with_empty_data(self, capsys):
        """Test notification with empty data."""
        adapter = ConsoleNotificationAdapter()

        await adapter.send_notification("Title", "Message", {})

        captured = capsys.readouterr()
        assert "Title" in captured.out
        assert "Message" in captured.out
        # Should not print "Data:" section for empty data

    @pytest.mark.asyncio
    async def test_formatted_output(self, capsys):
        """Test that output is properly formatted."""
        adapter = ConsoleNotificationAdapter()

        await adapter.send_greeting_notification("Alice", "Hello, Alice!")

        captured = capsys.readouterr()
        # Check for consistent formatting
        assert "─" in captured.out  # Separator line
        assert "To:" in captured.out
        assert "Message:" in captured.out
