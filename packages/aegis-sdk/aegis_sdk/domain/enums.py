"""Domain enums for type safety and consistency.

This module centralizes all enumeration types used across the SDK,
ensuring type safety and preventing string literal errors.
"""

from enum import Enum


class ServiceStatus(str, Enum):
    """Service instance status enumeration.

    Represents the operational state of a service instance.
    """

    ACTIVE = "ACTIVE"  # Service is running normally
    STANDBY = "STANDBY"  # Service is ready but not actively processing
    UNHEALTHY = "UNHEALTHY"  # Service has issues but still running
    SHUTDOWN = "SHUTDOWN"  # Service is shutting down


class SubscriptionMode(str, Enum):
    """Event subscription mode enumeration.

    Determines how events are distributed among service instances.
    """

    COMPETE = "compete"  # Load-balanced: only one instance processes each event
    BROADCAST = "broadcast"  # All instances receive and process the event


class CommandPriority(str, Enum):
    """Command priority levels.

    Used to prioritize command processing in queues.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other: "CommandPriority") -> bool:
        """Enable priority comparison."""
        if not isinstance(other, CommandPriority):
            return NotImplemented

        priority_order = [self.LOW, self.NORMAL, self.HIGH, self.CRITICAL]
        return priority_order.index(self) < priority_order.index(other)


class StickyActiveStatus(str, Enum):
    """Sticky active election status.

    Represents the state of a service instance in leader election.
    """

    ACTIVE = "ACTIVE"  # Instance is the active leader
    STANDBY = "STANDBY"  # Instance is standby, ready to take over
    ELECTING = "ELECTING"  # Instance is participating in election


class ServiceLifecycleState(str, Enum):
    """Service lifecycle state enumeration.

    Represents the various states a service goes through during its lifecycle.
    """

    INITIALIZING = "INITIALIZING"  # Service is being initialized
    STARTING = "STARTING"  # Service is starting up
    STARTED = "STARTED"  # Service is running normally
    STOPPING = "STOPPING"  # Service is shutting down
    STOPPED = "STOPPED"  # Service has stopped
    FAILED = "FAILED"  # Service encountered a fatal error
