"""Commands for test-example."""

from pydantic import BaseModel


class Command(BaseModel):
    """Base command class."""

    correlation_id: str | None = None


class CreateUserCommand(Command):
    """Create user command."""

    name: str
    email: str


class UpdateEmailCommand(Command):
    """Update email command."""

    user_id: str
    new_email: str


class DeleteUserCommand(Command):
    """Delete user command."""

    user_id: str
