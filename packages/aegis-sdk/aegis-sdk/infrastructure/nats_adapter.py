"""NATS adapter - Concrete implementation of MessageBusPort."""

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

import nats
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext

from ..application.metrics import get_metrics
from ..domain.models import Command, Event, RPCRequest, RPCResponse
from ..domain.patterns import SubjectPatterns
from ..ports.message_bus import MessageBusPort
from .serialization import (
    SerializationError,
    deserialize_params,
    detect_and_deserialize,
    is_msgpack,
    serialize_dict,
    serialize_to_msgpack,
)


class NATSAdapter(MessageBusPort):
    """NATS implementation of the message bus port."""

    def __init__(self, pool_size: int = 1, use_msgpack: bool = True):
        """Initialize NATS adapter.

        Args:
            pool_size: Number of connections to maintain (default: 1)
            use_msgpack: Whether to use MessagePack for serialization (default: True)
        """
        self._pool_size = pool_size
        self._connections: list[NATSClient] = []
        self._js: JetStreamContext | None = None
        self._current_conn = 0
        self._metrics = get_metrics()
        self._use_msgpack = use_msgpack

    async def connect(self, servers: list[str]) -> None:
        """Connect to NATS servers with clustering support."""
        # Create connections
        for i in range(self._pool_size):
            nc = await nats.connect(
                servers=servers,
                max_reconnect_attempts=10,
                reconnect_time_wait=2.0,
            )
            self._connections.append(nc)

        # Initialize JetStream on first connection
        if self._connections:
            self._js = self._connections[0].jetstream()

            # Ensure streams exist
            await self._ensure_streams()

        self._metrics.gauge("nats.connections", len(self._connections))
        print(f"✅ Connected to NATS cluster with {len(self._connections)} connections")

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        for nc in self._connections:
            if nc.is_connected:
                await nc.close()
        self._connections.clear()
        self._metrics.gauge("nats.connections", 0)

    async def is_connected(self) -> bool:
        """Check if connected to NATS."""
        return any(nc.is_connected for nc in self._connections)

    def _get_connection(self) -> NATSClient:
        """Get next available connection (round-robin)."""
        if not self._connections:
            raise Exception("Not connected to NATS")

        # Round-robin through connections
        conn = self._connections[self._current_conn]
        self._current_conn = (self._current_conn + 1) % len(self._connections)

        # Find a connected one
        attempts = 0
        while not conn.is_connected and attempts < len(self._connections):
            self._current_conn = (self._current_conn + 1) % len(self._connections)
            conn = self._connections[self._current_conn]
            attempts += 1

        if not conn.is_connected:
            raise Exception("No active NATS connections")

        return conn

    async def _ensure_streams(self) -> None:
        """Ensure JetStream streams exist."""
        if not self._js:
            return

        # Event stream
        try:
            await self._js.stream_info("EVENTS")
        except:
            await self._js.add_stream(
                name="EVENTS",
                subjects=["events.>"],
                retention="limits",
                max_msgs=100000,
            )

        # Command stream
        try:
            await self._js.stream_info("COMMANDS")
        except:
            await self._js.add_stream(
                name="COMMANDS",
                subjects=["commands.>"],
                retention="workqueue",
                max_msgs=10000,
            )

    # RPC Implementation
    async def register_rpc_handler(
        self, service: str, method: str, handler: Callable[[dict[str, Any]], Any]
    ) -> None:
        """Register an RPC handler."""

        async def wrapper(msg):
            with self._metrics.timer(f"rpc.{service}.{method}"):
                try:
                    # Parse request
                    if isinstance(msg.data, bytes):
                        try:
                            request = detect_and_deserialize(msg.data, RPCRequest)
                        except SerializationError:
                            # Try the other format if auto-detection fails
                            data = msg.data.decode()
                            request = RPCRequest(**json.loads(data))
                    else:
                        data = msg.data
                        request = RPCRequest(**json.loads(data))

                    # Call handler
                    result = await handler(request.params)

                    # Create response
                    response = RPCResponse(
                        correlation_id=request.message_id,
                        success=True,
                        result=result,
                    )

                    # Send response
                    if self._use_msgpack:
                        await msg.respond(serialize_to_msgpack(response))
                    else:
                        await msg.respond(response.model_dump_json().encode())
                    self._metrics.increment(f"rpc.{service}.{method}.success")

                except Exception as e:
                    # Error response
                    response = RPCResponse(
                        correlation_id=request.message_id if "request" in locals() else None,
                        success=False,
                        error=str(e),
                    )
                    if self._use_msgpack:
                        await msg.respond(serialize_to_msgpack(response))
                    else:
                        await msg.respond(response.model_dump_json().encode())
                    self._metrics.increment(f"rpc.{service}.{method}.error")

        # Subscribe with queue group for load balancing
        subject = SubjectPatterns.rpc(service, method)
        queue_group = f"rpc.{service}"
        # Only subscribe on first connection with queue group
        await self._connections[0].subscribe(subject, queue=queue_group, cb=wrapper)

    async def call_rpc(self, request: RPCRequest) -> RPCResponse:
        """Make an RPC call."""
        nc = self._get_connection()

        # Extract service and method from request
        parts = request.target.split(".")
        if len(parts) >= 2:
            service = parts[0]
            method = request.method
        else:
            service = request.target
            method = request.method

        subject = SubjectPatterns.rpc(service, method)

        with self._metrics.timer(f"rpc.client.{service}.{method}"):
            try:
                # Send request
                if self._use_msgpack:
                    request_data = serialize_to_msgpack(request)
                else:
                    request_data = request.model_dump_json().encode()

                response_msg = await nc.request(
                    subject,
                    request_data,
                    timeout=request.timeout,
                )

                # Parse response
                if isinstance(response_msg.data, bytes):
                    response = detect_and_deserialize(response_msg.data, RPCResponse)
                else:
                    data = response_msg.data
                    response = RPCResponse(**json.loads(data))
                self._metrics.increment(f"rpc.client.{service}.{method}.success")
                return response

            except TimeoutError:
                self._metrics.increment(f"rpc.client.{service}.{method}.timeout")
                return RPCResponse(
                    correlation_id=request.message_id,
                    success=False,
                    error=f"Timeout calling {service}.{method}",
                )
            except Exception as e:
                self._metrics.increment(f"rpc.client.{service}.{method}.error")
                return RPCResponse(
                    correlation_id=request.message_id,
                    success=False,
                    error=str(e),
                )

    # Event Implementation
    async def subscribe_event(
        self, pattern: str, handler: Callable[[Event], None], durable: str | None = None
    ) -> None:
        """Subscribe to events."""
        if not self._js:
            raise Exception("JetStream not initialized")

        async def wrapper(msg):
            try:
                # Parse event
                if isinstance(msg.data, bytes):
                    event = detect_and_deserialize(msg.data, Event)
                else:
                    data = msg.data
                    event = Event(**json.loads(data))

                # Call handler
                await handler(event)

                # Acknowledge only if JetStream message
                if hasattr(msg, "ack"):
                    await msg.ack()
                self._metrics.increment(f"events.processed.{event.domain}.{event.event_type}")

            except Exception as e:
                print(f"Event handler error: {e}")

                if hasattr(msg, "nak"):
                    await msg.nak()
                self._metrics.increment("events.errors")

        # Subscribe with JetStream for durable subscription
        # For event patterns, use core NATS if pattern contains wildcards
        if "*" in pattern or ">" in pattern:
            # Use core NATS for wildcard subscriptions
            nc = self._get_connection()
            await nc.subscribe(pattern, cb=wrapper)
        else:
            # Use JetStream for specific subjects
            await self._js.subscribe(
                pattern,
                cb=wrapper,
                durable=durable,
                manual_ack=True,
            )

    async def publish_event(self, event: Event) -> None:
        """Publish an event with retry logic for NATS client issues."""
        if not self._js:
            raise Exception("JetStream not initialized")

        subject = SubjectPatterns.event(event.domain, event.event_type)

        with self._metrics.timer(f"events.publish.{event.domain}.{event.event_type}"):
            if self._use_msgpack:
                event_data = serialize_to_msgpack(event)
            else:
                event_data = event.model_dump_json().encode()

            # Retry logic for empty response issue in NATS client
            max_retries = 3
            retry_delay = 0.01  # 10ms

            for attempt in range(max_retries):
                try:
                    ack = await self._js.publish(
                        subject,
                        event_data,
                    )
                    self._metrics.increment(f"events.published.{event.domain}.{event.event_type}")
                    return  # Success
                except json.JSONDecodeError as e:
                    # This is the empty response issue from NATS server
                    if attempt < max_retries - 1:
                        # Retry with exponential backoff
                        await asyncio.sleep(retry_delay * (2**attempt))
                        continue
                    else:
                        # Final attempt failed, raise the error
                        self._metrics.increment("events.publish.json_errors")
                        raise Exception(
                            f"JetStream publish failed after {max_retries} attempts: {e}"
                        )
                except Exception:
                    # Other errors, don't retry
                    raise

    # Command Implementation
    async def register_command_handler(
        self, service: str, command: str, handler: Callable[[Command, Callable], Any]
    ) -> None:
        """Register a command handler."""
        if not self._js:
            raise Exception("JetStream not initialized")

        async def wrapper(msg):
            try:
                # Parse command
                if isinstance(msg.data, bytes):
                    cmd = detect_and_deserialize(msg.data, Command)
                else:
                    data = msg.data
                    cmd = Command(**json.loads(data))

                # Progress reporter
                async def report_progress(percent: float, status: str = "processing"):
                    progress_data = {
                        "command_id": cmd.message_id,
                        "progress": percent,
                        "status": status,
                        "timestamp": time.time(),
                    }
                    nc = self._get_connection()
                    await nc.publish(
                        SubjectPatterns.command_progress(cmd.message_id),
                        serialize_dict(progress_data, self._use_msgpack),
                    )

                # Call handler
                with self._metrics.timer(f"commands.{service}.{command}"):
                    result = await handler(cmd, report_progress)

                # Send completion
                completion_data = {
                    "command_id": cmd.message_id,
                    "status": "completed",
                    "result": result,
                }

                nc = self._get_connection()
                await nc.publish(
                    SubjectPatterns.command_callback(cmd.message_id),
                    serialize_dict(completion_data, self._use_msgpack),
                )

                # Acknowledge
                await msg.ack()
                self._metrics.increment(f"commands.processed.{service}.{command}")

            except Exception as e:
                print(f"Command handler error: {e}")
                await msg.nak()
                self._metrics.increment("commands.errors")

        # Subscribe with JetStream
        subject = SubjectPatterns.command(service, command)
        await self._js.subscribe(
            subject,
            cb=wrapper,
            durable=f"{service}-{command}",
            manual_ack=True,
        )

    async def send_command(self, command: Command, track_progress: bool = True) -> dict[str, Any]:
        """Send a command."""
        if not self._js:
            raise Exception("JetStream not initialized")

        service = command.target or "unknown"
        subject = SubjectPatterns.command(service, command.command)

        # Track progress if requested
        if track_progress:
            progress_updates = []
            completion_data = None

            async def progress_handler(msg):
                if isinstance(msg.data, bytes) and is_msgpack(msg.data):
                    progress_updates.append(deserialize_params(msg.data, self._use_msgpack))
                else:
                    progress_updates.append(json.loads(msg.data.decode()))

            async def completion_handler(msg):
                nonlocal completion_data
                if isinstance(msg.data, bytes) and is_msgpack(msg.data):
                    completion_data = deserialize_params(msg.data, self._use_msgpack)
                else:
                    completion_data = json.loads(msg.data.decode())

            # Subscribe to progress
            nc = self._get_connection()
            progress_sub = await nc.subscribe(
                SubjectPatterns.command_progress(command.message_id),
                cb=progress_handler,
            )
            completion_sub = await nc.subscribe(
                SubjectPatterns.command_callback(command.message_id),
                cb=completion_handler,
            )

        # Send command with retry logic
        with self._metrics.timer(f"commands.send.{service}.{command.command}"):
            if self._use_msgpack:
                command_data = serialize_to_msgpack(command)
            else:
                command_data = command.model_dump_json().encode()

            # Retry logic for empty response issue in NATS client
            max_retries = 3
            retry_delay = 0.01  # 10ms

            for attempt in range(max_retries):
                try:
                    ack = await self._js.publish(
                        subject,
                        command_data,
                    )
                    break  # Success
                except json.JSONDecodeError as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2**attempt))
                        continue
                    else:
                        self._metrics.increment("commands.send.json_errors")
                        raise Exception(
                            f"JetStream publish failed after {max_retries} attempts: {e}"
                        )

        if track_progress:
            # Wait for completion
            start_time = time.time()
            while completion_data is None and (time.time() - start_time) < command.timeout:
                await asyncio.sleep(0.1)

            # Cleanup
            await progress_sub.unsubscribe()
            await completion_sub.unsubscribe()

            return completion_data or {"error": "Command timeout"}
        else:
            return {"command_id": command.message_id, "stream": ack.stream, "seq": ack.seq}

    # Service Registration
    async def register_service(self, service_name: str, instance_id: str) -> None:
        """Register service instance."""
        nc = self._get_connection()
        registration_data = {
            "service_name": service_name,
            "instance_id": instance_id,
            "timestamp": time.time(),
        }
        await nc.publish(
            SubjectPatterns.registry_register(),
            json.dumps(registration_data).encode(),
        )
        self._metrics.increment("services.registered")

    async def unregister_service(self, service_name: str, instance_id: str) -> None:
        """Unregister service instance."""
        nc = self._get_connection()
        unregistration_data = {
            "service_name": service_name,
            "instance_id": instance_id,
            "timestamp": time.time(),
        }
        await nc.publish(
            SubjectPatterns.registry_unregister(),
            json.dumps(unregistration_data).encode(),
        )
        self._metrics.increment("services.unregistered")

    async def send_heartbeat(self, service_name: str, instance_id: str) -> None:
        """Send service heartbeat."""
        nc = self._get_connection()
        heartbeat_data = {
            "instance_id": instance_id,
            "timestamp": time.time(),
            "metrics": self._metrics.get_all(),
        }
        await nc.publish(
            SubjectPatterns.heartbeat(service_name),
            json.dumps(heartbeat_data).encode(),
        )
        self._metrics.increment("heartbeats.sent")
