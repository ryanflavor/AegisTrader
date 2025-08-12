"""Domain entities for market-service."""

from datetime import datetime

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """Base class for all entities."""

    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = None

    class Config:
        frozen = False


class User(Entity):
    """User entity."""

    name: str
    email: str

    def update_email(self, email: str) -> None:
        """Update user email."""
        self.email = email
        self.updated_at = datetime.now()


class Order(Entity):
    """Order entity."""

    user_id: str
    total_amount: float
    status: str = "pending"

    def confirm(self) -> None:
        """Confirm the order."""
        self.status = "confirmed"
        self.updated_at = datetime.now()
