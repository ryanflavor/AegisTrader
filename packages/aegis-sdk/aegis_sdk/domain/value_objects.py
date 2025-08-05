"""Domain value objects following Domain-Driven Design principles.

These value objects encapsulate domain concepts and provide type safety,
validation, and clear business meaning to what would otherwise be primitive types.
"""

import re
from datetime import datetime, timedelta
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import CommandPriority


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

    LOW: ClassVar[str] = CommandPriority.LOW.value
    NORMAL: ClassVar[str] = CommandPriority.NORMAL.value
    HIGH: ClassVar[str] = CommandPriority.HIGH.value
    CRITICAL: ClassVar[str] = CommandPriority.CRITICAL.value

    value: str = Field(
        default=CommandPriority.NORMAL.value,
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


class Version(BaseModel):
    """Value object representing a semantic version.

    Encapsulates version information with major, minor, and patch components
    following semantic versioning principles.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    major: int = Field(..., ge=0, description="Major version number")
    minor: int = Field(default=0, ge=0, description="Minor version number")
    patch: int = Field(default=0, ge=0, description="Patch version number")

    @classmethod
    def from_string(cls, version_string: str) -> "Version":
        """Create a Version from a string representation.

        Args:
            version_string: Version string in format "major.minor.patch" or partial

        Returns:
            Version instance

        Raises:
            ValueError: If the version string format is invalid
        """
        parts = version_string.split(".")

        if not 1 <= len(parts) <= 3:
            raise ValueError(f"Invalid version format: {version_string}")

        try:
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
        except ValueError as e:
            raise ValueError(f"Invalid version format: {version_string}") from e

        return cls(major=major, minor=minor, patch=patch)

    def __str__(self) -> str:
        """String representation in semantic version format."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: object) -> bool:
        """Less than comparison."""
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: object) -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other: object) -> bool:
        """Greater than comparison."""
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other: object) -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if isinstance(other, Version):
            return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash((self.major, self.minor, self.patch))

    def is_compatible_with(self, other: "Version") -> bool:
        """Check if this version is compatible with another version.

        Following semantic versioning, versions are compatible if they have
        the same major version number.

        Args:
            other: Version to compare with

        Returns:
            True if versions are compatible (same major version)
        """
        return self.major == other.major

    def bump_major(self) -> "Version":
        """Return a new version with major version incremented.

        When bumping major version, minor and patch are reset to 0.
        """
        return Version(major=self.major + 1, minor=0, patch=0)

    def bump_minor(self) -> "Version":
        """Return a new version with minor version incremented.

        When bumping minor version, patch is reset to 0.
        """
        return Version(major=self.major, minor=self.minor + 1, patch=0)

    def bump_patch(self) -> "Version":
        """Return a new version with patch version incremented."""
        return Version(major=self.major, minor=self.minor, patch=self.patch + 1)


class Duration(BaseModel):
    """Value object representing a time duration.

    Encapsulates time duration with various conversion methods and
    arithmetic operations. Always non-negative.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    seconds: float = Field(..., ge=0, description="Duration in seconds")

    @field_validator("seconds")
    @classmethod
    def validate_non_negative(cls, v: float) -> float:
        """Ensure duration is non-negative."""
        if v < 0:
            raise ValueError("Duration must be non-negative")
        return v

    @classmethod
    def from_milliseconds(cls, milliseconds: float) -> "Duration":
        """Create Duration from milliseconds."""
        return cls(seconds=milliseconds / 1000)

    @classmethod
    def from_minutes(cls, minutes: float) -> "Duration":
        """Create Duration from minutes."""
        return cls(seconds=minutes * 60)

    @classmethod
    def from_hours(cls, hours: float) -> "Duration":
        """Create Duration from hours."""
        return cls(seconds=hours * 3600)

    @classmethod
    def from_timedelta(cls, td: timedelta) -> "Duration":
        """Create Duration from Python timedelta."""
        return cls(seconds=td.total_seconds())

    def total_seconds(self) -> float:
        """Get total seconds (same as seconds attribute)."""
        return self.seconds

    def to_milliseconds(self) -> float:
        """Convert to milliseconds."""
        return self.seconds * 1000

    def to_minutes(self) -> float:
        """Convert to minutes."""
        return self.seconds / 60

    def to_hours(self) -> float:
        """Convert to hours."""
        return self.seconds / 3600

    def to_timedelta(self) -> timedelta:
        """Convert to Python timedelta."""
        return timedelta(seconds=self.seconds)

    def is_zero(self) -> bool:
        """Check if duration is zero."""
        return self.seconds == 0

    def __str__(self) -> str:
        """Human-readable string representation."""
        total_seconds = int(self.seconds)

        # Handle fractional seconds for small durations
        if self.seconds < 1:
            return f"{self.seconds}s"

        # Calculate components
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        # Build string
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:  # Always show seconds if no other parts
            # Show fractional part if original had fractions
            if self.seconds != total_seconds:
                parts.append(f"{self.seconds}s")
            else:
                parts.append(f"{seconds}s")

        return " ".join(parts)

    def __add__(self, other: object) -> "Duration":
        """Add two durations."""
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(seconds=self.seconds + other.seconds)

    def __sub__(self, other: object) -> "Duration":
        """Subtract two durations."""
        if not isinstance(other, Duration):
            return NotImplemented
        result = self.seconds - other.seconds
        if result < 0:
            raise ValueError("Duration must be non-negative")
        return Duration(seconds=result)

    def __mul__(self, scalar: float) -> "Duration":
        """Multiply duration by a scalar."""
        return Duration(seconds=self.seconds * scalar)

    def __truediv__(self, scalar: float) -> "Duration":
        """Divide duration by a scalar."""
        if scalar == 0:
            raise ValueError("Cannot divide by zero")
        return Duration(seconds=self.seconds / scalar)

    def __lt__(self, other: object) -> bool:
        """Less than comparison."""
        if not isinstance(other, Duration):
            return NotImplemented
        return self.seconds < other.seconds

    def __le__(self, other: object) -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, Duration):
            return NotImplemented
        return self.seconds <= other.seconds

    def __gt__(self, other: object) -> bool:
        """Greater than comparison."""
        if not isinstance(other, Duration):
            return NotImplemented
        return self.seconds > other.seconds

    def __ge__(self, other: object) -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, Duration):
            return NotImplemented
        return self.seconds >= other.seconds

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if isinstance(other, Duration):
            return self.seconds == other.seconds
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash(self.seconds)


class StickyActiveStatus(BaseModel):
    """Value object representing the sticky active status of a service.

    Encapsulates the election state for sticky single-active pattern.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    ACTIVE: ClassVar[str] = "ACTIVE"
    STANDBY: ClassVar[str] = "STANDBY"
    ELECTING: ClassVar[str] = "ELECTING"

    value: str = Field(
        ...,
        pattern="^(ACTIVE|STANDBY|ELECTING)$",
        description="The sticky active status",
    )

    def __str__(self) -> str:
        """String representation returns the value."""
        return self.value

    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if isinstance(other, StickyActiveStatus):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash(self.value)

    def is_active(self) -> bool:
        """Check if status is ACTIVE."""
        return self.value == self.ACTIVE

    def is_standby(self) -> bool:
        """Check if status is STANDBY."""
        return self.value == self.STANDBY

    def is_electing(self) -> bool:
        """Check if status is ELECTING."""
        return self.value == self.ELECTING


class LeaderKey(BaseModel):
    """Value object representing a sticky active leader key.

    Encapsulates the key used for leader election in NATS KV Store.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    service_name: ServiceName
    group_id: str = Field(default="default", description="Service group identifier")

    def to_kv_key(self) -> str:
        """Convert to NATS KV Store key format."""
        return f"sticky-active.{self.service_name.value}.{self.group_id}.leader"

    def __str__(self) -> str:
        """String representation returns the KV key."""
        return self.to_kv_key()


class ElectionTimeout(BaseModel):
    """Value object representing election timeout configuration.

    Encapsulates timing parameters for leader election and failover.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    leader_ttl: Duration = Field(
        default_factory=lambda: Duration(seconds=5),
        description="TTL for leader key in KV Store",
    )
    heartbeat_interval: Duration = Field(
        default_factory=lambda: Duration(seconds=2),
        description="Interval between leader heartbeats",
    )
    election_timeout: Duration = Field(
        default_factory=lambda: Duration(seconds=10),
        description="Maximum time to wait for election completion",
    )
    failover_delay: Duration = Field(
        default_factory=lambda: Duration(seconds=0.5),
        description="Delay before attempting to take over leadership",
    )

    @field_validator("heartbeat_interval")
    @classmethod
    def validate_heartbeat_interval(cls, v: Duration, info) -> Duration:
        """Ensure heartbeat interval is less than leader TTL."""
        if "leader_ttl" in info.data:
            leader_ttl = info.data["leader_ttl"]
            if v.seconds >= leader_ttl.seconds:
                raise ValueError("Heartbeat interval must be less than leader TTL")
        return v


class ServiceGroupId(BaseModel):
    """Value object representing a service group identifier.

    Used to group service instances for sticky active election.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    value: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="The service group identifier",
    )

    @field_validator("value")
    @classmethod
    def validate_group_id(cls, v: str) -> str:
        """Validate group ID format.

        Group IDs must:
        - Not contain whitespace
        - Not contain dots (reserved for key hierarchy)
        """
        if not v.strip():
            raise ValueError("Group ID cannot be empty or whitespace")
        if "." in v:
            raise ValueError("Group ID cannot contain dots")
        if any(c.isspace() for c in v):
            raise ValueError("Group ID cannot contain whitespace")
        return v

    def __str__(self) -> str:
        """String representation returns the value."""
        return self.value

    def __eq__(self, other: Any) -> bool:
        """Equality comparison."""
        if isinstance(other, ServiceGroupId):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash(self.value)


class Timestamp(BaseModel):
    """Value object representing a point in time.

    Encapsulates a timezone-aware datetime with convenience methods
    for conversion and manipulation. Always requires timezone information.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    value: datetime = Field(..., description="The timestamp value")

    @field_validator("value")
    @classmethod
    def validate_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        return v

    @classmethod
    def now(cls) -> "Timestamp":
        """Create a timestamp for the current time in UTC."""
        from datetime import UTC, datetime

        return cls(value=datetime.now(UTC))

    @classmethod
    def from_iso_string(cls, iso_string: str) -> "Timestamp":
        """Create timestamp from ISO format string.

        Args:
            iso_string: ISO format datetime string

        Returns:
            Timestamp instance

        Raises:
            ValueError: If the string format is invalid
        """
        from datetime import datetime

        try:
            # Handle Z suffix for UTC
            if iso_string.endswith("Z"):
                iso_string = iso_string[:-1] + "+00:00"
            dt = datetime.fromisoformat(iso_string)
            return cls(value=dt)
        except ValueError as e:
            raise ValueError(f"Invalid ISO timestamp format: {iso_string}") from e

    @classmethod
    def from_unix(cls, unix_timestamp: float) -> "Timestamp":
        """Create timestamp from Unix timestamp (seconds since epoch).

        Args:
            unix_timestamp: Seconds since Unix epoch

        Returns:
            Timestamp instance in UTC
        """
        from datetime import UTC, datetime

        dt = datetime.fromtimestamp(unix_timestamp, tz=UTC)
        return cls(value=dt)

    def to_iso_string(self, use_z_suffix: bool = False) -> str:
        """Convert to ISO format string.

        Args:
            use_z_suffix: Use 'Z' instead of '+00:00' for UTC

        Returns:
            ISO format datetime string
        """
        iso_str = self.value.isoformat()
        if use_z_suffix and iso_str.endswith("+00:00"):
            return iso_str[:-6] + "Z"
        return iso_str

    def to_unix(self) -> float:
        """Convert to Unix timestamp (seconds since epoch)."""
        return self.value.timestamp()

    def to_utc(self) -> "Timestamp":
        """Convert timestamp to UTC timezone.

        Returns:
            New Timestamp instance in UTC
        """
        from datetime import UTC

        return Timestamp(value=self.value.astimezone(UTC))

    def add(self, duration: "Duration") -> "Timestamp":
        """Add a duration to this timestamp.

        Args:
            duration: Duration to add

        Returns:
            New Timestamp instance
        """
        new_dt = self.value + duration.to_timedelta()
        return Timestamp(value=new_dt)

    def subtract(self, duration: "Duration") -> "Timestamp":
        """Subtract a duration from this timestamp.

        Args:
            duration: Duration to subtract

        Returns:
            New Timestamp instance
        """
        new_dt = self.value - duration.to_timedelta()
        return Timestamp(value=new_dt)

    def diff(self, other: "Timestamp") -> "Duration":
        """Calculate the duration between this and another timestamp.

        Args:
            other: Timestamp to compare to

        Returns:
            Duration between the timestamps (always positive)
        """
        delta = abs((self.value - other.value).total_seconds())
        return Duration(seconds=delta)

    def is_before(self, other: "Timestamp") -> bool:
        """Check if this timestamp is before another."""
        return self.value < other.value

    def is_after(self, other: "Timestamp") -> bool:
        """Check if this timestamp is after another."""
        return self.value > other.value

    def __str__(self) -> str:
        """String representation returns ISO format."""
        return self.to_iso_string()

    def __lt__(self, other: object) -> bool:
        """Less than comparison."""
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: object) -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: object) -> bool:
        """Greater than comparison."""
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other: object) -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.value >= other.value

    def __eq__(self, other: object) -> bool:
        """Equality comparison."""
        if isinstance(other, Timestamp):
            return self.value == other.value
        return False

    def __hash__(self) -> int:
        """Make hashable for use in sets and dicts."""
        return hash(self.value)
