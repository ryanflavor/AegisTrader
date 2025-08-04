"""Shared technical contracts for AegisTrader services.

This package contains technical contracts and constants used across
all AegisTrader services. It does NOT contain business domain models.

Business domain models should be defined within each service's own domain.
"""

from __future__ import annotations

from shared_contracts.constants import (
    EventPatterns,
    KVBuckets,
    RPCPatterns,
    ServiceDefaults,
    ServiceNames,
)
from shared_contracts.message_contracts import (
    BaseEventContract,
    EventMetadata,
    RPCRequestContract,
    RPCResponseContract,
    ServiceHealthContract,
    ServiceMetricsContract,
)
from shared_contracts.utils import parse_event_pattern

__all__ = [
    # Constants
    "ServiceNames",
    "EventPatterns",
    "KVBuckets",
    "RPCPatterns",
    "ServiceDefaults",
    # Message Contracts
    "BaseEventContract",
    "EventMetadata",
    "RPCRequestContract",
    "RPCResponseContract",
    "ServiceHealthContract",
    "ServiceMetricsContract",
    # Utils
    "parse_event_pattern",
]
