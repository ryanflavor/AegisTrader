"""
Gateway adapter components.

These components are extracted from the monolithic BaseGatewayAdapter
to follow Single Responsibility Principle.
"""

from .connection_manager import ConnectionManager
from .event_dispatcher import EventDispatcher
from .query_scheduler import QueryScheduler

__all__ = [
    "ConnectionManager",
    "EventDispatcher",
    "QueryScheduler",
]
