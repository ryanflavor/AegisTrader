"""Domain value objects following Domain-Driven Design principles.

These value objects encapsulate domain concepts and provide type safety,
validation, and clear business meaning to what would otherwise be primitive types.
"""

import re
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceName(BaseModel):
    """Value object representing a service name.

    Ensures service names follow consistent naming conventions and
    provides type safety for service identification.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    value: str = Field(..., min_length=1, max_length=64, description="The service name")

    @field_validator("value")
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        """Validate service name format.

        Service names must:
        - Start with a letter
        - Contain only letters, numbers, hyphens, and underscores
        - Not end with a hyphen or underscore
        """
        pattern = r"^[a-zA-Z][a-zA-Z0-9_-]*[a-zA-Z0-9]$|^[a-zA-Z]$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid service name '{v}'. Must start with a letter, "
                "contain only letters, numbers, hyphens, and underscores, "
                "and not end with a hyphen or underscore."
            )
        return v.lower()  # Normalize to lowercase

    def __str__(self) -> str:
        """String representation returns the value."""
        return self.value

    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if isinstance(other, ServiceName):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash(self.value)


class InstanceId(BaseModel):
    """Value object representing a service instance identifier.

    Provides type safety and validation for instance identification.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    value: str = Field(..., min_length=1, max_length=128, description="The instance identifier")

    @field_validator("value")
    @classmethod
    def validate_instance_id(cls, v: str) -> str:
        """Validate instance ID format.

        Instance IDs must not contain whitespace or control characters.
        """
        if not v.strip():
            raise ValueError("Instance ID cannot be empty or whitespace")
        if any(c.isspace() or ord(c) < 32 for c in v):
            raise ValueError("Instance ID cannot contain whitespace or control characters")
        return v

    def __str__(self) -> str:
        """String representation returns the value."""
        return self.value

    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if isinstance(other, InstanceId):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash(self.value)


class EventType(BaseModel):
    """Value object representing an event type.

    Ensures event types follow consistent naming conventions and
    provides type safety for event handling.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    value: str = Field(..., min_length=1, max_length=64, description="The event type")

    @field_validator("value")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """Validate event type format.

        Event types must:
        - Contain only letters, numbers, dots, and underscores
        - Not start or end with a dot
        - Not contain consecutive dots
        """
        pattern = r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid event type '{v}'. Must contain only letters, numbers, "
                "dots, and underscores, and follow dot notation (e.g., 'order.created')"
            )
        return v.lower()  # Normalize to lowercase

    def __str__(self) -> str:
        """String representation returns the value."""
        return self.value

    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if isinstance(other, EventType):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash(self.value)

    @property
    def domain(self) -> str:
        """Extract the domain from the event type.

        For example, 'order.created' returns 'order'.
        """
        parts = self.value.split(".")
        return parts[0] if parts else ""

    @property
    def action(self) -> str:
        """Extract the action from the event type.

        For example, 'order.created' returns 'created'.
        """
        parts = self.value.split(".")
        return parts[-1] if len(parts) > 1 else parts[0]


class MethodName(BaseModel):
    """Value object representing an RPC method name.

    Ensures method names follow consistent conventions.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    value: str = Field(..., min_length=1, max_length=64, description="The method name")

    @field_validator("value")
    @classmethod
    def validate_method_name(cls, v: str) -> str:
        """Validate method name format.

        Method names must:
        - Start with a letter
        - Contain only letters, numbers, and underscores
        - Follow snake_case convention
        """
        pattern = r"^[a-z][a-z0-9_]*$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid method name '{v}'. Must start with a lowercase letter "
                "and follow snake_case convention."
            )
        return v

    def __str__(self) -> str:
        """String representation returns the value."""
        return self.value

    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if isinstance(other, MethodName):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash(self.value)


class Priority(BaseModel):
    """Value object representing command priority.

    Encapsulates priority levels with type safety.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    LOW: ClassVar[str] = "low"
    NORMAL: ClassVar[str] = "normal"
    HIGH: ClassVar[str] = "high"
    CRITICAL: ClassVar[str] = "critical"

    value: str = Field(
        default=NORMAL,
        pattern="^(low|normal|high|critical)$",
        description="The priority level",
    )

    def __str__(self) -> str:
        """String representation returns the value."""
        return self.value

    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if isinstance(other, Priority):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash(self.value)

    def __lt__(self, other: object) -> bool:
        """Allow priority comparison."""
        if not isinstance(other, Priority):
            return NotImplemented
        priority_order = [self.LOW, self.NORMAL, self.HIGH, self.CRITICAL]
        return priority_order.index(self.value) < priority_order.index(other.value)


class SanitizedKey(BaseModel):
    """Value object representing a sanitized NATS-compatible key.

    NATS KV keys cannot contain: spaces, tabs, '.', '*', '>', '/', '\\'
    This value object ensures keys are properly sanitized and tracks
    the mapping between original and sanitized keys.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    original: str = Field(..., min_length=1, description="Original key value")
    sanitized: str = Field(..., min_length=1, description="Sanitized key value")

    # NATS invalid characters as a class constant
    INVALID_CHARS: ClassVar[list[str]] = [" ", "\t", ".", "*", ">", "/", "\\", ":"]
    REPLACEMENT_CHAR: ClassVar[str] = "_"

    @field_validator("original")
    @classmethod
    def validate_original_not_empty(cls, v: str) -> str:
        """Ensure original key is not empty after stripping."""
        if not v.strip():
            raise ValueError("Key cannot be empty or contain only whitespace")
        return v

    @classmethod
    def create(cls, key: str, sanitize: bool = True) -> "SanitizedKey":
        """Factory method to create a sanitized key.

        Args:
            key: The original key value
            sanitize: Whether to apply sanitization (default: True)

        Returns:
            SanitizedKey instance
        """
        if not sanitize:
            return cls(original=key, sanitized=key)

        sanitized = key
        for char in cls.INVALID_CHARS:
            sanitized = sanitized.replace(char, cls.REPLACEMENT_CHAR)

        return cls(original=key, sanitized=sanitized)

    @property
    def was_sanitized(self) -> bool:
        """Check if the key was modified during sanitization."""
        return self.original != self.sanitized

    def __str__(self) -> str:
        """Return the sanitized key for string operations."""
        return self.sanitized

    def __repr__(self) -> str:
        """Return detailed representation."""
        return f"SanitizedKey(original='{self.original}', sanitized='{self.sanitized}')"

    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if isinstance(other, SanitizedKey):
            return self.original == other.original and self.sanitized == other.sanitized
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash((self.original, self.sanitized))
