"""Port interface for election repository.

This interface defines the contract for election repositories
following the hexagonal architecture pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..domain.aggregates import StickyActiveElection
from ..domain.value_objects import InstanceId, ServiceName


class ElectionRepository(ABC):
    """Repository interface for sticky active election management.

    This repository handles the persistence and retrieval of election state
    using atomic operations to ensure consistency across distributed instances.
    """

    @abstractmethod
    async def attempt_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        ttl_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Attempt to acquire leadership using atomic create-or-get operation.

        Args:
            service_name: Name of the service
            instance_id: Instance attempting to become leader
            group_id: Service group identifier
            ttl_seconds: TTL for the leader key
            metadata: Optional metadata to store with leader info

        Returns:
            True if leadership was acquired, False otherwise
        """
        ...

    @abstractmethod
    async def update_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
        ttl_seconds: int,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update existing leadership with heartbeat.

        This operation should only succeed if the instance is the current leader.

        Args:
            service_name: Name of the service
            instance_id: Instance updating leadership
            group_id: Service group identifier
            ttl_seconds: TTL for the leader key
            metadata: Optional metadata to update

        Returns:
            True if update succeeded, False if not the leader
        """
        ...

    @abstractmethod
    async def get_current_leader(
        self,
        service_name: ServiceName,
        group_id: str,
    ) -> tuple[InstanceId | None, dict[str, Any]]:
        """Get the current leader information.

        Args:
            service_name: Name of the service
            group_id: Service group identifier

        Returns:
            Tuple of (leader_instance_id, metadata)
            Returns (None, {}) if no leader exists
        """
        ...

    @abstractmethod
    async def release_leadership(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> bool:
        """Release leadership voluntarily.

        This operation should only succeed if the instance is the current leader.

        Args:
            service_name: Name of the service
            instance_id: Instance releasing leadership
            group_id: Service group identifier

        Returns:
            True if leadership was released, False if not the leader
        """
        ...

    @abstractmethod
    async def watch_leadership(
        self,
        service_name: ServiceName,
        group_id: str,
    ):
        """Watch for leadership changes.

        This is an async generator that yields leadership change events.

        Args:
            service_name: Name of the service
            group_id: Service group identifier

        Yields:
            Leadership change events with structure:
            {
                "type": "elected" | "lost" | "expired",
                "leader_id": str | None,
                "metadata": dict,
                "timestamp": float
            }
        """
        ...

    @abstractmethod
    async def save_election_state(
        self,
        election: StickyActiveElection,
    ) -> None:
        """Save the election aggregate state.

        Args:
            election: The election aggregate to persist
        """
        ...

    @abstractmethod
    async def get_election_state(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> StickyActiveElection | None:
        """Retrieve the election aggregate state.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Service group identifier

        Returns:
            The election aggregate or None if not found
        """
        ...

    @abstractmethod
    async def delete_election_state(
        self,
        service_name: ServiceName,
        instance_id: InstanceId,
        group_id: str,
    ) -> None:
        """Delete the election aggregate state.

        Args:
            service_name: Name of the service
            instance_id: Instance identifier
            group_id: Service group identifier
        """
        ...
