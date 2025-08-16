"""
Election factory that uses SDK's fixed election repository.

Maximizes SDK reuse by leveraging the existing fix in aegis-sdk.
"""

from aegis_sdk.infrastructure.in_memory_metrics import InMemoryMetrics
from aegis_sdk.infrastructure.nats_kv_election_repository import NatsKvElectionRepository
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger
from aegis_sdk.ports.election_repository import ElectionRepository
from aegis_sdk.ports.factory_ports import ElectionRepositoryFactory as BaseElectionRepositoryFactory
from aegis_sdk.ports.message_bus import MessageBusPort


class ElectionFactory(BaseElectionRepositoryFactory):
    """Factory that uses SDK's fixed election repository implementation."""

    async def create_election_repository(
        self,
        service_name: str,
        message_bus: MessageBusPort,
        logger=None,
    ) -> ElectionRepository:
        """Create election repository using SDK's fixed implementation.

        Args:
            service_name: Name of the service for the election
            message_bus: Message bus for NATS connection
            logger: Optional logger instance

        Returns:
            SDK's FixedNatsKvElectionRepository instance
        """
        # Create KV store
        kv_store = NATSKVStore(message_bus)
        await kv_store.connect(f"election_{service_name.replace('-', '_')}")

        # Use provided logger or create one
        if logger is None:
            logger = SimpleLogger(f"{service_name}.election")

        # Return SDK's implementation directly
        return NatsKvElectionRepository(
            kv_store=kv_store,
            logger=logger,
            metrics=InMemoryMetrics(),
        )
