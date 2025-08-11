"""NATS adapter - Concrete implementation of MessageBusPort."""

import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

import nats
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg
from nats.js import JetStreamContext

from ..domain.metrics_models import MetricsSnapshot
from ..domain.models import Command, Event, RPCRequest, RPCResponse
from ..domain.patterns import SubjectPatterns
from ..domain.value_objects import InstanceId, ServiceName
from ..ports.message_bus import MessageBusPort
from ..ports.metrics import MetricsPort
from .config import LogContext, NATSConnectionConfig
from .factories import SerializationFactory
from .in_memory_metrics import InMemoryMetrics
from .serialization import (
    SerializationError,
    deserialize_params,
    detect_and_deserialize,
    is_msgpack,
    serialize_dict,
)


class NATSAdapter(MessageBusPort):
    """NATS implementation of the message bus port."""

    def __init__(
        self,
        config: NATSConnectionConfig | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize NATS adapter with configuration.

        Args:
            config: Connection configuration. If not provided, uses defaults.
            metrics: Optional metrics port. If not provided, uses default adapter.
        """
        self._config = config or NATSConnectionConfig()
        self._connections: list[NATSClient] = []
        self._js: JetStreamContext | None = None
        self._current_conn = 0
        self._metrics = metrics or InMemoryMetrics()
        self._serializer = SerializationFactory.create_serializer(self._config.use_msgpack)

        # Extract service identification from config
        self._service_name = str(self._config.service_name) if self._config.service_name else None
        self._instance_id = str(self._config.instance_id) if self._config.instance_id else None

    async def connect(self, servers: list[str] | None = None) -> None:
        """Connect to NATS servers with clustering support.

        Args:
            servers: Optional override for server URLs. If not provided, uses config.
        """
        # Use provided servers or fall back to config
        connect_servers = servers or self._config.servers

        # Create connections
        for _i in range(self._config.pool_size):
            # Get connection params and override servers if provided
            conn_params = self._config.to_connection_params()
            conn_params["servers"] = connect_servers

            nc = await nats.connect(**conn_params)
            self._connections.append(nc)

        # Initialize JetStream on first connection
        if self._connections and self._config.enable_jetstream:
            # Use JS domain from config or environment
            js_domain = self._config.js_domain or os.getenv("NATS_JS_DOMAIN")
            if js_domain:
                self._js = self._connections[0].jetstream(domain=js_domain)
            else:
                self._js = self._connections[0].jetstream()

            # Ensure streams exist
            await self._ensure_streams()

        self._metrics.gauge("nats.connections", len(self._connections))

        # Log with context
        log_ctx = LogContext(
            service_name=self._service_name,
            instance_id=self._instance_id,
            operation="connect",
            component="NATSAdapter",
        )
        print(
            f"✅ Connected to NATS cluster with {len(self._connections)} connections - {log_ctx.to_dict()}"
        )

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
        except Exception:
            await self._js.add_stream(
                name="EVENTS",
                subjects=["events.>"],
                retention="limits",
                max_msgs=100000,
            )

        # Command stream
        try:
            await self._js.stream_info("COMMANDS")
        except Exception:
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

        async def wrapper(msg: Msg) -> None:
            with self._metrics.timer(f"rpc.{service}.{method}"):
                try:
                    # Parse request - msg.data is always bytes in NATS
                    try:
                        request = detect_and_deserialize(msg.data, RPCRequest)
                    except SerializationError:
                        # Try the other format if auto-detection fails
                        data = msg.data.decode()
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
                    await msg.respond(self._serializer.serialize(response))
                    self._metrics.increment(f"rpc.{service}.{method}.success")

                except Exception as e:
                    # Error response
                    response = RPCResponse(
                        correlation_id=(request.message_id if "request" in locals() else None),
                        success=False,
                        error=str(e),
                    )
                    await msg.respond(self._serializer.serialize(response))
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
        if request.target:
            parts = request.target.split(".")
            if len(parts) >= 2:
                service = parts[0]
                method = request.method
            else:
                service = request.target
                method = request.method
        else:
            # Default to using method name if no target specified
            service = "unknown"
            method = request.method

        subject = SubjectPatterns.rpc(service, method)

        with self._metrics.timer(f"rpc.client.{service}.{method}"):
            try:
                # Send request
                request_data = self._serializer.serialize(request)

                response_msg = await nc.request(
                    subject,
                    request_data,
                    timeout=request.timeout,
                )

                # Parse response - response_msg.data is always bytes in NATS
                response = detect_and_deserialize(response_msg.data, RPCResponse)
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
        self,
        pattern: str,
        handler: Callable[[Event], Awaitable[None]],
        durable: str | None = None,
        mode: str = "compete",
    ) -> None:
        """Subscribe to events with compete or broadcast mode.

        Args:
            pattern: Event pattern to subscribe to
            handler: Handler function for events
            durable: Base durable subscription name
            mode: "compete" for load balanced or "broadcast" for all instances
        """
        if not self._js:
            raise Exception("JetStream not initialized")

        # Validate mode
        valid_modes = ["compete", "broadcast"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}")

        async def wrapper(msg: Msg) -> None:
            try:
                # Parse event - msg.data is always bytes in NATS
                event = detect_and_deserialize(msg.data, Event)

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

            # For compete mode with wildcards, use queue group
            if mode == "compete" and self._service_name:
                await nc.subscribe(pattern, queue=self._service_name, cb=wrapper)
            else:
                # Broadcast mode or no service name
                await nc.subscribe(pattern, cb=wrapper)
        else:
            # Use JetStream for specific subjects
            subscribe_kwargs = {
                "subject": pattern,
                "cb": wrapper,
                "manual_ack": True,
            }

            # Configure based on mode
            if mode == "compete":
                # Use queue for load balancing
                # In NATS JetStream, when using queue, it becomes the durable name
                if self._service_name:
                    subscribe_kwargs["queue"] = self._service_name
                    # Don't set durable when using queue - they conflict
                else:
                    # Without service name, just use durable
                    subscribe_kwargs["durable"] = durable
            else:  # broadcast mode
                # Create unique durable per instance
                if durable and self._instance_id:
                    subscribe_kwargs["durable"] = f"{durable}-{self._instance_id}"
                elif durable:
                    subscribe_kwargs["durable"] = durable
                # No queue for broadcast

            await self._js.subscribe(**subscribe_kwargs)

    async def publish_event(self, event: Event) -> None:
        """Publish an event with retry logic for NATS client issues."""
        if not self._js:
            raise Exception("JetStream not initialized")

        subject = SubjectPatterns.event(event.domain, event.event_type)

        with self._metrics.timer(f"events.publish.{event.domain}.{event.event_type}"):
            event_data = self._serializer.serialize(event)

            # Retry logic for empty response issue in NATS client
            max_retries = 3
            retry_delay = 0.01  # 10ms

            for attempt in range(max_retries):
                try:
                    await self._js.publish(
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
                        ) from e
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

        async def wrapper(msg: Msg) -> None:
            try:
                # Parse command
                # Parse command - msg.data is always bytes in NATS
                cmd = detect_and_deserialize(msg.data, Command)

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
                        serialize_dict(progress_data, self._config.use_msgpack),
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
                    serialize_dict(completion_data, self._config.use_msgpack),
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

            async def progress_handler(msg: Msg) -> None:
                if isinstance(msg.data, bytes) and is_msgpack(msg.data):
                    progress_updates.append(deserialize_params(msg.data, self._config.use_msgpack))
                else:
                    progress_updates.append(json.loads(msg.data.decode()))

            async def completion_handler(msg: Msg) -> None:
                nonlocal completion_data
                if isinstance(msg.data, bytes) and is_msgpack(msg.data):
                    completion_data = deserialize_params(msg.data, self._config.use_msgpack)
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
            command_data = self._serializer.serialize(command)

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
                        ) from e

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
            return {
                "command_id": command.message_id,
                "stream": ack.stream,
                "seq": ack.seq,
            }

    # Service Registration
    async def register_service(self, service_name: str, instance_id: str) -> None:
        """Register service instance."""
        # Validate inputs using value objects
        service = ServiceName(value=service_name)
        instance = InstanceId(value=instance_id)

        # Store for use in event subscriptions
        self._service_name = str(service)
        self._instance_id = str(instance)

        nc = self._get_connection()
        registration_data = {
            "service_name": str(service),
            "instance_id": str(instance),
            "timestamp": time.time(),
        }
        await nc.publish(
            SubjectPatterns.registry_register(),
            json.dumps(registration_data).encode(),
        )
        self._metrics.increment("services.registered")

    async def unregister_service(self, service_name: str, instance_id: str) -> None:
        """Unregister service instance."""
        # Validate inputs using value objects
        service = ServiceName(value=service_name)
        instance = InstanceId(value=instance_id)

        nc = self._get_connection()
        unregistration_data = {
            "service_name": str(service),
            "instance_id": str(instance),
            "timestamp": time.time(),
        }
        await nc.publish(
            SubjectPatterns.registry_unregister(),
            json.dumps(unregistration_data).encode(),
        )
        self._metrics.increment("services.unregistered")

    async def send_heartbeat(self, service_name: str, instance_id: str) -> None:
        """Send service heartbeat."""
        # Validate inputs using value objects
        service = ServiceName(value=service_name)
        instance = InstanceId(value=instance_id)

        nc = self._get_connection()

        # Get metrics snapshot using proper domain model
        metrics_data = self._metrics.get_all()
        if isinstance(metrics_data, MetricsSnapshot):
            metrics_snapshot = metrics_data
        else:
            # Fallback for dict format (backward compatibility)
            metrics_snapshot = MetricsSnapshot(
                uptime_seconds=metrics_data.get("uptime", 0.0),
                counters=metrics_data.get("counters", {}),
                gauges=metrics_data.get("gauges", {}),
                summaries=metrics_data.get("summaries", {}),
            )

        heartbeat_data = {
            "instance_id": str(instance),
            "timestamp": time.time(),
            "metrics": metrics_snapshot.model_dump(),
        }
        await nc.publish(
            SubjectPatterns.heartbeat(str(service)),
            json.dumps(heartbeat_data).encode(),
        )
        self._metrics.increment("heartbeats.sent")
