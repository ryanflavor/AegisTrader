"""
AegisSDK - Minimal IPC SDK based on pure NATS.

A lightweight SDK following hexagonal architecture and DDD principles.
Built on the lessons learned from pure NATS implementations.
"""

__version__ = "0.1.0"

from .application.service import Service
from .domain.models import Command, Event, Message, RPCRequest, RPCResponse
from .domain.patterns import SubjectPatterns

__all__ = [
    "Command",
    "Event",
    "Message",
    "RPCRequest",
    "RPCResponse",
    "Service",
    "SubjectPatterns",
]
