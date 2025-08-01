"""Tests for domain patterns."""

from aegis_sdk.domain.patterns import SubjectPatterns


class TestSubjectPatterns:
    """Test cases for SubjectPatterns."""

    def test_rpc_pattern(self):
        """Test RPC subject pattern generation."""
        assert SubjectPatterns.rpc("user", "get") == "rpc.user.get"
        assert (
            SubjectPatterns.rpc("order-service", "create_order")
            == "rpc.order-service.create_order"
        )
        assert SubjectPatterns.rpc("a", "b") == "rpc.a.b"

    def test_event_pattern(self):
        """Test event subject pattern generation."""
        assert SubjectPatterns.event("order", "created") == "events.order.created"
        assert SubjectPatterns.event("user", "updated") == "events.user.updated"
        assert (
            SubjectPatterns.event("payment", "processed") == "events.payment.processed"
        )

    def test_command_pattern(self):
        """Test command subject pattern generation."""
        assert (
            SubjectPatterns.command("processor", "batch") == "commands.processor.batch"
        )
        assert SubjectPatterns.command("worker", "task") == "commands.worker.task"
        assert SubjectPatterns.command("service", "action") == "commands.service.action"

    def test_service_instance_pattern(self):
        """Test service instance subject pattern."""
        assert SubjectPatterns.service_instance("api", "inst-1") == "service.api.inst-1"
        assert (
            SubjectPatterns.service_instance("worker", "abc123")
            == "service.worker.abc123"
        )

    def test_heartbeat_pattern(self):
        """Test heartbeat subject pattern."""
        assert SubjectPatterns.heartbeat("api") == "internal.heartbeat.api"
        assert (
            SubjectPatterns.heartbeat("order-service")
            == "internal.heartbeat.order-service"
        )

    def test_registry_patterns(self):
        """Test registry subject patterns."""
        assert SubjectPatterns.registry_register() == "internal.registry.register"
        assert SubjectPatterns.registry_unregister() == "internal.registry.unregister"

    def test_route_request_pattern(self):
        """Test route request pattern."""
        assert SubjectPatterns.route_request() == "internal.route.request"

    def test_command_lifecycle_patterns(self):
        """Test command lifecycle patterns."""
        cmd_id = "123e4567-e89b-12d3-a456-426614174000"

        assert SubjectPatterns.command_progress(cmd_id) == f"commands.progress.{cmd_id}"
        assert SubjectPatterns.command_callback(cmd_id) == f"commands.callback.{cmd_id}"
        assert SubjectPatterns.command_cancel(cmd_id) == f"commands.cancel.{cmd_id}"

    def test_is_valid_service_name(self):
        """Test service name validation."""
        # Valid service names
        assert SubjectPatterns.is_valid_service_name("api") is True
        assert SubjectPatterns.is_valid_service_name("order-service") is True
        assert SubjectPatterns.is_valid_service_name("user_service") is True
        assert SubjectPatterns.is_valid_service_name("Service123") is True
        assert SubjectPatterns.is_valid_service_name("a") is True

        # Invalid service names
        assert SubjectPatterns.is_valid_service_name("") is False
        assert (
            SubjectPatterns.is_valid_service_name("123service") is False
        )  # starts with number
        assert (
            SubjectPatterns.is_valid_service_name("-service") is False
        )  # starts with dash
        assert (
            SubjectPatterns.is_valid_service_name("_service") is False
        )  # starts with underscore
        assert (
            SubjectPatterns.is_valid_service_name("service.name") is False
        )  # contains dot
        assert (
            SubjectPatterns.is_valid_service_name("service name") is False
        )  # contains space
        assert (
            SubjectPatterns.is_valid_service_name("service@name") is False
        )  # contains special char

    def test_is_valid_method_name(self):
        """Test method name validation."""
        # Valid method names
        assert SubjectPatterns.is_valid_method_name("get") is True
        assert SubjectPatterns.is_valid_method_name("getUserById") is True
        assert SubjectPatterns.is_valid_method_name("get_user_by_id") is True
        assert SubjectPatterns.is_valid_method_name("Method123") is True
        assert SubjectPatterns.is_valid_method_name("a") is True

        # Invalid method names
        assert SubjectPatterns.is_valid_method_name("") is False
        assert (
            SubjectPatterns.is_valid_method_name("123method") is False
        )  # starts with number
        assert (
            SubjectPatterns.is_valid_method_name("-method") is False
        )  # starts with dash
        assert (
            SubjectPatterns.is_valid_method_name("method-name") is False
        )  # contains dash
        assert (
            SubjectPatterns.is_valid_method_name("method.name") is False
        )  # contains dot
        assert (
            SubjectPatterns.is_valid_method_name("method name") is False
        )  # contains space
        assert (
            SubjectPatterns.is_valid_method_name("method@name") is False
        )  # contains special char

    def test_pattern_consistency(self):
        """Test that patterns are consistent and predictable."""
        # Test that patterns follow a consistent structure
        service = "test-service"
        method = "test_method"
        domain = "test-domain"
        event_type = "test-event"
        command = "test-command"
        instance = "test-instance"

        # All patterns should start with their category
        assert SubjectPatterns.rpc(service, method).startswith("rpc.")
        assert SubjectPatterns.event(domain, event_type).startswith("events.")
        assert SubjectPatterns.command(service, command).startswith("commands.")
        assert SubjectPatterns.service_instance(service, instance).startswith(
            "service."
        )
        assert SubjectPatterns.heartbeat(service).startswith("internal.heartbeat.")

        # Registry patterns should be under internal
        assert SubjectPatterns.registry_register().startswith("internal.registry.")
        assert SubjectPatterns.registry_unregister().startswith("internal.registry.")
        assert SubjectPatterns.route_request().startswith("internal.route.")

        # Command lifecycle patterns should be under commands
        assert SubjectPatterns.command_progress("id").startswith("commands.progress.")
        assert SubjectPatterns.command_callback("id").startswith("commands.callback.")
        assert SubjectPatterns.command_cancel("id").startswith("commands.cancel.")

    def test_pattern_edge_cases(self):
        """Test edge cases in pattern generation."""
        # Empty strings should still generate valid patterns
        assert SubjectPatterns.rpc("", "") == "rpc.."
        assert SubjectPatterns.event("", "") == "events.."
        assert SubjectPatterns.command("", "") == "commands.."

        # Special characters in IDs
        special_id = "id-with_special.chars"
        assert (
            SubjectPatterns.command_progress(special_id)
            == f"commands.progress.{special_id}"
        )
        assert (
            SubjectPatterns.command_callback(special_id)
            == f"commands.callback.{special_id}"
        )
        assert (
            SubjectPatterns.command_cancel(special_id)
            == f"commands.cancel.{special_id}"
        )
