"""Single active service implementation for exclusive RPC execution."""

import asyncio
import time
from collections.abc import Callable
from functools import wraps

from ..domain.models import Event
from .service import Service


class SingleActiveService(Service):
    """Service with single active instance support.

    Only one instance can execute exclusive RPC methods at a time.
    Uses simple heartbeat-based election without external dependencies.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_active = False
        self.last_active_heartbeat = 0
        self._election_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start service and election process."""
        await super().start()

        # Subscribe to election events
        @self.subscribe(f"service.{self.service_name}.election")
        async def handle_election(event: Event):
            if event.payload.get("instance_id") != self.instance_id:
                # Another instance is active
                self.is_active = False
                self.last_active_heartbeat = time.time()

        # Start election process
        self._election_task = asyncio.create_task(self._run_election())

    async def stop(self) -> None:
        """Stop service and election."""
        if self._election_task:
            self._election_task.cancel()
        await super().stop()

    async def _run_election(self) -> None:
        """Simple election: if no heartbeat for 5s, become active."""
        while True:
            try:
                if not self.is_active and time.time() - self.last_active_heartbeat > 5:
                    # No active instance, become active
                    self.is_active = True
                    print(f"✓ {self.instance_id} became active")

                if self.is_active:
                    # Send heartbeat
                    await self.publish_event(
                        f"service.{self.service_name}.election",
                        "heartbeat",
                        {"instance_id": self.instance_id},
                    )

                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Election error: {e}")
                await asyncio.sleep(1)

    def exclusive_rpc(self, method: str):
        """Instance method decorator for exclusive RPC handlers."""

        def decorator(handler: Callable):
            @wraps(handler)
            async def wrapper(params: dict) -> dict:
                if not self.is_active:
                    return {
                        "success": False,
                        "error": "NOT_ACTIVE",
                        "message": "This instance is not active. Please retry.",
                    }
                return await handler(params)

            # Register with parent class
            self._rpc_handlers[method] = wrapper
            return wrapper

        return decorator


def exclusive_rpc(method: str):
    """Decorator to mark RPC methods that require single active instance."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self: SingleActiveService, params: dict) -> dict:
            if not isinstance(self, SingleActiveService):
                # Fallback for regular services
                return await func(self, params)

            if not self.is_active:
                return {
                    "success": False,
                    "error": "NOT_ACTIVE",
                    "message": "This instance is not active. Please retry.",
                }

            return await func(self, params)

        # Mark as exclusive for registration
        wrapper._exclusive = True
        return wrapper

    # Handle both @exclusive_rpc and @exclusive_rpc("method_name")
    if callable(method):
        return decorator(method)

    def outer_decorator(func: Callable) -> Callable:
        wrapped = decorator(func)
        wrapped._rpc_method = method
        return wrapped

    return outer_decorator
