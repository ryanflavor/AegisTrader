"""Domain models for Hello World service using Pydantic v2."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class Greeting(BaseModel):
    """Value object representing a greeting."""

    message: str = Field(..., min_length=1, max_length=500, description="The greeting message")
    language: str = Field(default="en", pattern="^[a-z]{2}$", description="ISO 639-1 language code")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Ensure message is not just whitespace."""
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace")
        return v.strip()

    model_config = {"frozen": True, "strict": True}


class HelloRequest(BaseModel):
    """Entity representing a hello request."""

    id: UUID = Field(default_factory=uuid4, description="Unique request identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Name to greet")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Request timestamp"
    )
    greeting_style: str = Field(default="formal", description="Style of greeting")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Sanitize and validate name."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        # Remove any control characters
        cleaned = "".join(char for char in cleaned if char.isprintable())
        return cleaned

    @field_validator("greeting_style")
    @classmethod
    def validate_style(cls, v: str) -> str:
        """Validate greeting style."""
        valid_styles = {"formal", "casual", "friendly", "professional"}
        if v not in valid_styles:
            raise ValueError(f"Greeting style must be one of {valid_styles}")
        return v

    def to_greeting(self) -> Greeting:
        """Convert request to a greeting based on style."""
        messages = {
            "formal": f"Good day, {self.name}. How may I assist you?",
            "casual": f"Hey {self.name}! What's up?",
            "friendly": f"Hello {self.name}! Nice to see you!",
            "professional": f"Greetings, {self.name}. Welcome to our service.",
        }
        return Greeting(message=messages[self.greeting_style])

    model_config = {"strict": True}


class HelloResponse(BaseModel):
    """Value object representing the response to a hello request."""

    request_id: UUID = Field(..., description="ID of the original request")
    greeting: Greeting = Field(..., description="The generated greeting")
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Processing timestamp"
    )
    service_version: str = Field(default="1.0.0", description="Service version")
    processing_time_ms: float | None = Field(None, description="Processing time in milliseconds")

    @field_validator("processing_time_ms")
    @classmethod
    def validate_processing_time(cls, v: float | None) -> float | None:
        """Ensure processing time is positive if provided."""
        if v is not None and v < 0:
            raise ValueError("Processing time must be non-negative")
        return v

    model_config = {"frozen": True, "strict": True}


class ServiceStatus(BaseModel):
    """Aggregate representing the service status."""

    healthy: bool = Field(..., description="Service health status")
    uptime_seconds: float = Field(..., ge=0, description="Service uptime in seconds")
    requests_processed: int = Field(default=0, ge=0, description="Total requests processed")
    last_request_at: datetime | None = Field(None, description="Timestamp of last request")
    version: str = Field(default="1.0.0", description="Service version")

    def increment_requests(self) -> None:
        """Increment the request counter and update timestamp."""
        self.requests_processed += 1
        self.last_request_at = datetime.now(timezone.utc)

    model_config = {"strict": True}
