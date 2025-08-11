"""Port interfaces for monitoring components.

This module defines the contracts for monitoring services including
heartbeat monitoring and election coordination, following hexagonal architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..domain.value_objects import ElectionState


class HeartbeatMonitorPort(ABC):
    """Port interface for heartbeat monitoring services.

    This interface defines the contract for monitoring service heartbeats
    and triggering elections when failures are detected.
    """

    @abstractmethod
    async def start_monitoring(self) -> None:
        """Start monitoring heartbeats.

        Begins the heartbeat monitoring process, watching for leader failures
        and triggering elections when necessary.
        """
        ...

    @abstractmethod
    async def stop_monitoring(self) -> None:
        """Stop monitoring heartbeats.

        Stops the heartbeat monitoring process and cleans up resources.
        """
        ...

    @abstractmethod
    def set_election_trigger(self, election_coordinator: ElectionCoordinatorPort) -> None:
        """Set the election coordinator to trigger on failure detection.

        Args:
            election_coordinator: The coordinator to trigger elections
        """
        ...

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """Get the current monitoring status.

        Returns:
            Dictionary containing monitoring status information
        """
        ...


class ElectionCoordinatorPort(ABC):
    """Port interface for election coordination services.

    This interface defines the contract for coordinating leader elections
    in a distributed system.
    """

    @abstractmethod
    async def start_election(self) -> bool:
        """Start a leader election.

        Attempts to become the leader through an election process.

        Returns:
            True if elected as leader, False otherwise
        """
        ...

    @abstractmethod
    async def check_leadership(self) -> bool:
        """Check if there is a current leader.

        Returns:
            True if a leader exists, False otherwise
        """
        ...

    @abstractmethod
    async def release_leadership(self) -> None:
        """Release leadership voluntarily.

        Releases the current leadership position if held.
        """
        ...

    @abstractmethod
    def is_elected(self) -> bool:
        """Check if this instance is the current leader.

        Returns:
            True if this instance is the leader, False otherwise
        """
        ...

    @abstractmethod
    def set_on_elected_callback(self, callback: Callable[[], Any]) -> None:
        """Set callback for when elected as leader.

        Args:
            callback: Function to call when elected
        """
        ...

    @abstractmethod
    def set_on_lost_callback(self, callback: Callable[[], Any]) -> None:
        """Set callback for when leadership is lost.

        Args:
            callback: Function to call when leadership is lost
        """
        ...

    @abstractmethod
    def get_election_state(self) -> ElectionState:
        """Get the current election state.

        Returns:
            The current election aggregate state
        """
        ...
