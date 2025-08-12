"""Command and query handlers for test-example."""

from typing import Any


class CommandHandler:
    """Handles commands."""

    def __init__(self, repository, event_bus):
        self._repository = repository
        self._event_bus = event_bus

    async def handle_create_user(self, command) -> str:
        """Handle create user command."""
        # Create user entity
        # Save to repository
        # Publish event
        return "user_id"

    async def handle_update_email(self, command) -> None:
        """Handle update email command."""
        # Load user
        # Update email
        # Save changes
        # Publish event
        pass

    async def handle_delete_user(self, command) -> None:
        """Handle delete user command."""
        # Delete user
        # Publish event
        pass


class QueryHandler:
    """Handles queries."""

    def __init__(self, read_model):
        self._read_model = read_model

    async def handle_get_user(self, query) -> dict[str, Any] | None:
        """Handle get user query."""
        # Query read model
        return None

    async def handle_search_users(self, query) -> list[dict[str, Any]]:
        """Handle search users query."""
        # Search read model
        return []
