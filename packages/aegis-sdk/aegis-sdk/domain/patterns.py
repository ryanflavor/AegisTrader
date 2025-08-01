"""Subject pattern management for NATS messaging."""


class SubjectPatterns:
    """Centralized subject pattern management following DDD principles."""

    # Application communication patterns
    @staticmethod
    def rpc(service: str, method: str) -> str:
        """Generate RPC subject pattern."""
        return f"rpc.{service}.{method}"

    @staticmethod
    def event(domain: str, event_type: str) -> str:
        """Generate event subject pattern."""
        return f"events.{domain}.{event_type}"

    @staticmethod
    def command(service: str, command: str) -> str:
        """Generate command subject pattern."""
        return f"commands.{service}.{command}"

    @staticmethod
    def service_instance(service: str, instance: str) -> str:
        """Generate service instance subject."""
        return f"service.{service}.{instance}"

    # Internal system patterns
    @staticmethod
    def heartbeat(service: str) -> str:
        """Generate heartbeat subject."""
        return f"internal.heartbeat.{service}"

    @staticmethod
    def registry_register() -> str:
        """Service registration subject."""
        return "internal.registry.register"

    @staticmethod
    def registry_unregister() -> str:
        """Service unregistration subject."""
        return "internal.registry.unregister"

    @staticmethod
    def route_request() -> str:
        """Routing request subject."""
        return "internal.route.request"

    # Command lifecycle patterns
    @staticmethod
    def command_progress(command_id: str) -> str:
        """Command progress update subject."""
        return f"commands.progress.{command_id}"

    @staticmethod
    def command_callback(command_id: str) -> str:
        """Command completion callback subject."""
        return f"commands.callback.{command_id}"

    @staticmethod
    def command_cancel(command_id: str) -> str:
        """Command cancellation subject."""
        return f"commands.cancel.{command_id}"

    # Pattern validation
    @staticmethod
    def is_valid_service_name(name: str) -> bool:
        """Validate service name format."""
        import re

        return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9-_]*$", name))

    @staticmethod
    def is_valid_method_name(name: str) -> bool:
        """Validate method name format."""
        import re

        return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", name))
