"""AegisSDK - Minimal IPC SDK based on pure NATS."""

from .application.service import Service
from .infrastructure.nats_adapter import NATSAdapter

__all__ = ["NATSAdapter", "Service"]
__version__ = "0.1.0"
