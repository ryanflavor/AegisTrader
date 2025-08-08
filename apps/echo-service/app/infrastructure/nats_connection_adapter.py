"""NATS connection adapter for Echo Service using aegis-sdk-dev patterns.

This adapter provides NATS connectivity following hexagonal architecture,
using the patterns from aegis-sdk-dev for proper isolation and testability.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import nats
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class NATSConnectionConfig(BaseModel):
    """Configuration for NATS connection with strict validation."""

    model_config = ConfigDict(frozen=True, strict=True)

    url: str = Field(..., description="NATS server URL")
    name: str = Field(default="echo-service", description="Client name")
    connect_timeout: float = Field(default=5.0, gt=0, description="Connection timeout in seconds")
    reconnect_time_wait: float = Field(default=2.0, gt=0, description="Reconnect wait time")
    max_reconnect_attempts: int = Field(default=60, ge=0, description="Max reconnect attempts")
    ping_interval: int = Field(default=120, gt=0, description="Ping interval in seconds")
    max_outstanding_pings: int = Field(default=2, gt=0, description="Max outstanding pings")


class NATSConnectionAdapter:
    """Adapter for NATS connection operations following hexagonal architecture.

    This adapter encapsulates all NATS connectivity logic, providing a clean
    interface to the application layer while handling connection management,
    reconnection, and error handling.
    """

    def __init__(self, config: NATSConnectionConfig) -> None:
        """Initialize NATS connection adapter.

        Args:
            config: NATS connection configuration
        """
        self._config = config
        self._client: NATSClient | None = None
        self._jetstream: JetStreamContext | None = None
        self._is_connected = False
        self._subscriptions: dict[str, Any] = {}

    async def connect(self) -> None:
        """Connect to NATS server.

        Raises:
            ConnectionError: If unable to connect to NATS
        """
        if self._is_connected:
            logger.warning("Already connected to NATS")
            return

        try:
            logger.info(f"Connecting to NATS at {self._config.url}")

            # Connection options
            options = {
                "servers": [self._config.url],
                "name": self._config.name,
                "connect_timeout": self._config.connect_timeout,
                "reconnect_time_wait": self._config.reconnect_time_wait,
                "max_reconnect_attempts": self._config.max_reconnect_attempts,
                "ping_interval": self._config.ping_interval,
                "max_outstanding_pings": self._config.max_outstanding_pings,
                "error_cb": self._error_callback,
                "disconnected_cb": self._disconnected_callback,
                "reconnected_cb": self._reconnected_callback,
                "closed_cb": self._closed_callback,
            }

            self._client = await nats.connect(**options)
            self._jetstream = self._client.jetstream()
            self._is_connected = True

            logger.info(f"Successfully connected to NATS at {self._config.url}")

        except TimeoutError as e:
            raise ConnectionError(
                f"Connection timeout after {self._config.connect_timeout}s"
            ) from e
        except Exception as e:
            raise ConnectionError(f"Failed to connect to NATS: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if not self._is_connected:
            return

        try:
            # Unsubscribe from all subscriptions
            for sub in self._subscriptions.values():
                await sub.unsubscribe()
            self._subscriptions.clear()

            # Close connection
            if self._client:
                await self._client.drain()
                await self._client.close()

            self._client = None
            self._jetstream = None
            self._is_connected = False

            logger.info("Disconnected from NATS")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            raise

    async def publish(self, subject: str, data: Any) -> None:
        """Publish message to a subject.

        Args:
            subject: NATS subject to publish to
            data: Data to publish (will be JSON encoded)

        Raises:
            ConnectionError: If not connected to NATS
        """
        if not self._is_connected or not self._client:
            raise ConnectionError("Not connected to NATS")

        try:
            # Encode data as JSON
            if isinstance(data, BaseModel):
                payload = data.model_dump_json().encode()
            elif isinstance(data, (dict, list)):
                payload = json.dumps(data).encode()
            elif isinstance(data, bytes):
                payload = data
            else:
                payload = str(data).encode()

            await self._client.publish(subject, payload)
            logger.debug(f"Published message to {subject}")

        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            raise

    async def request(self, subject: str, data: Any, timeout: float = 1.0) -> Any:
        """Send request and wait for response.

        Args:
            subject: NATS subject to send request to
            data: Request data
            timeout: Response timeout in seconds

        Returns:
            Response data

        Raises:
            ConnectionError: If not connected to NATS
            TimeoutError: If response timeout
        """
        if not self._is_connected or not self._client:
            raise ConnectionError("Not connected to NATS")

        try:
            # Encode request data
            if isinstance(data, BaseModel):
                payload = data.model_dump_json().encode()
            elif isinstance(data, (dict, list)):
                payload = json.dumps(data).encode()
            elif isinstance(data, bytes):
                payload = data
            else:
                payload = str(data).encode()

            # Send request and wait for response
            msg = await self._client.request(subject, payload, timeout=timeout)

            # Decode response
            try:
                return json.loads(msg.data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                return msg.data

        except TimeoutError as e:
            raise TimeoutError(f"Request timeout after {timeout}s") from e
        except Exception as e:
            logger.error(f"Request failed for {subject}: {e}")
            raise

    async def subscribe(
        self, subject: str, handler: Callable[[Any], Any], queue: str | None = None
    ) -> str:
        """Subscribe to a subject.

        Args:
            subject: NATS subject pattern to subscribe to
            handler: Async handler function for messages
            queue: Optional queue group name

        Returns:
            Subscription ID

        Raises:
            ConnectionError: If not connected to NATS
        """
        if not self._is_connected or not self._client:
            raise ConnectionError("Not connected to NATS")

        try:
            # Wrapper to decode messages before passing to handler
            async def message_handler(msg):
                try:
                    # Try to decode as JSON
                    data = json.loads(msg.data.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    data = msg.data

                # Call the handler
                result = await handler(data)

                # If handler returns a result and message has reply subject, respond
                if result is not None and msg.reply:
                    if isinstance(result, BaseModel):
                        response = result.model_dump_json().encode()
                    elif isinstance(result, (dict, list)):
                        response = json.dumps(result).encode()
                    else:
                        response = str(result).encode()
                    await msg.respond(response)

            # Subscribe with optional queue group
            if queue:
                sub = await self._client.subscribe(subject, queue=queue, cb=message_handler)
            else:
                sub = await self._client.subscribe(subject, cb=message_handler)

            # Store subscription
            sub_id = f"{subject}_{id(sub)}"
            self._subscriptions[sub_id] = sub

            logger.info(f"Subscribed to {subject} (queue: {queue or 'none'})")
            return sub_id

        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")
            raise

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from a subscription.

        Args:
            subscription_id: Subscription ID to unsubscribe
        """
        if subscription_id in self._subscriptions:
            sub = self._subscriptions[subscription_id]
            await sub.unsubscribe()
            del self._subscriptions[subscription_id]
            logger.debug(f"Unsubscribed from {subscription_id}")

    async def create_kv_bucket(self, bucket: str, ttl: int = 0) -> Any:
        """Create a JetStream KV bucket.

        Args:
            bucket: Bucket name
            ttl: TTL for entries in seconds (0 for no TTL)

        Returns:
            KV bucket handle

        Raises:
            ConnectionError: If not connected or JetStream not available
        """
        if not self._jetstream:
            raise ConnectionError("JetStream not available")

        try:
            config = nats.js.api.KeyValueConfig(
                bucket=bucket,
                ttl=ttl if ttl > 0 else None,
            )
            kv = await self._jetstream.create_key_value(config)
            logger.info(f"Created KV bucket: {bucket}")
            return kv
        except Exception as e:
            # Check if bucket already exists
            if "already exists" in str(e).lower():
                kv = await self._jetstream.key_value(bucket)
                logger.info(f"Using existing KV bucket: {bucket}")
                return kv
            raise

    async def get_kv_bucket(self, bucket: str) -> Any:
        """Get a JetStream KV bucket.

        Args:
            bucket: Bucket name

        Returns:
            KV bucket handle

        Raises:
            ConnectionError: If not connected or bucket doesn't exist
        """
        if not self._jetstream:
            raise ConnectionError("JetStream not available")

        try:
            return await self._jetstream.key_value(bucket)
        except Exception as e:
            raise ConnectionError(f"Failed to get KV bucket {bucket}: {e}") from e

    @property
    def is_connected(self) -> bool:
        """Check if connected to NATS."""
        return self._is_connected and self._client is not None and self._client.is_connected

    @property
    def client(self) -> NATSClient | None:
        """Get the underlying NATS client."""
        return self._client

    @property
    def jetstream(self) -> JetStreamContext | None:
        """Get the JetStream context."""
        return self._jetstream

    # Callback methods for connection events
    async def _error_callback(self, e: Exception) -> None:
        """Handle NATS errors."""
        logger.error(f"NATS error: {e}")

    async def _disconnected_callback(self) -> None:
        """Handle NATS disconnection."""
        logger.warning("Disconnected from NATS, will attempt to reconnect")
        self._is_connected = False

    async def _reconnected_callback(self) -> None:
        """Handle NATS reconnection."""
        logger.info("Reconnected to NATS")
        self._is_connected = True

    async def _closed_callback(self) -> None:
        """Handle NATS connection closed."""
        logger.info("NATS connection closed")
        self._is_connected = False
