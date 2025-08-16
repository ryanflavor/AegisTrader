"""
Connection Manager for vnpy gateways.

Manages gateway connection lifecycle, status tracking, and reconnection logic.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from vnpy.event import EventEngine
from vnpy.trader.gateway import BaseGateway

from domain.gateway.value_objects import AuthenticationCredentials

logger = logging.getLogger(__name__)


class ConnectionStatus(BaseModel):
    """Track connection status for MD and TD separately."""

    model_config = ConfigDict(strict=True)

    md_connected: bool = False
    md_login_status: bool = False
    md_last_error: str | None = None

    td_connected: bool = False
    td_login_status: bool = False
    td_auth_status: bool = False
    td_last_error: str | None = None

    login_failed: bool = False
    auth_failed: bool = False
    settlement_confirmed: bool = False

    last_heartbeat: datetime | None = None
    error_count: int = 0


class ConnectionConfig(BaseModel):
    """Configuration for connection management."""

    model_config = ConfigDict(strict=True)

    reconnect_interval: int = Field(default=5, description="Reconnect interval in seconds", gt=0)
    max_reconnect_attempts: int = Field(default=3, description="Max reconnect attempts", gt=0)
    heartbeat_interval: int = Field(default=30, description="Heartbeat interval in seconds", gt=0)
    connection_timeout: int = Field(default=30, description="Connection timeout in seconds", gt=0)
    enable_flow_control: bool = Field(default=True, description="Enable flow control handling")


class ConnectionManager:
    """
    Manages vnpy gateway connections.

    Responsibilities:
    - Connection lifecycle management
    - Status tracking
    - Heartbeat management
    - Reconnection logic
    """

    def __init__(
        self,
        executor: ThreadPoolExecutor,
        config: ConnectionConfig | dict | None = None,
    ):
        """
        Initialize connection manager.

        Args:
            executor: Thread pool executor for vnpy operations
            config: Connection configuration (dict or ConnectionConfig object)
        """
        self.executor = executor
        # Convert dict to ConnectionConfig if needed
        if isinstance(config, dict):
            self.config = ConnectionConfig(**config)
        else:
            self.config = config or ConnectionConfig()

        # Connection components
        self.event_engine: EventEngine | None = None
        self.gateway: BaseGateway | None = None

        # Connection status
        self.status = ConnectionStatus()

        # Async coordination
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._heartbeat_task: asyncio.Task | None = None

        # Gateway identification
        self.gateway_name: str = ""
        self.gateway_class: type[BaseGateway] | None = None

    def set_gateway_info(self, name: str, gateway_class: type[BaseGateway]) -> None:
        """
        Set gateway information.

        Args:
            name: Gateway name
            gateway_class: Gateway class type
        """
        self.gateway_name = name
        self.gateway_class = gateway_class

    def _init_event_engine_sync(self) -> EventEngine:
        """Initialize EventEngine in sync context."""
        engine = EventEngine()
        engine.start()
        logger.info("EventEngine created and started")
        return engine

    def _init_gateway_sync(self, event_engine: EventEngine) -> BaseGateway:
        """Initialize gateway in sync context."""
        if not self.gateway_class:
            raise ValueError("Gateway class not set")

        gateway = self.gateway_class(event_engine, self.gateway_name)
        logger.info(f"Initialized {self.gateway_name} gateway")
        return gateway

    def _connect_gateway_sync(self, gateway: BaseGateway, setting: dict[str, Any]) -> None:
        """Connect gateway in sync context."""
        gateway.connect(setting)
        logger.info(f"{self.gateway_name} gateway.connect() called")

    def _disconnect_gateway_sync(self, gateway: BaseGateway) -> None:
        """Disconnect gateway in sync context."""
        gateway.close()
        logger.info(f"{self.gateway_name} gateway closed")

    async def connect(
        self, credentials: AuthenticationCredentials, setting: dict[str, Any]
    ) -> None:
        """
        Connect to gateway.

        Args:
            credentials: Authentication credentials
            setting: Connection settings dictionary
        """
        logger.info(f"Connecting to {self.gateway_name}...")

        loop = asyncio.get_event_loop()
        self._main_loop = loop

        # Reset status
        self.status = ConnectionStatus()

        # Initialize EventEngine if needed
        if not self.event_engine:
            self.event_engine = await loop.run_in_executor(
                self.executor, self._init_event_engine_sync
            )

        # Initialize gateway if needed
        if not self.gateway:
            self.gateway = await loop.run_in_executor(
                self.executor, self._init_gateway_sync, self.event_engine
            )

        # Connect with flow control handling
        max_attempts = 3 if self.config.enable_flow_control else 1

        for attempt in range(max_attempts):
            try:
                await loop.run_in_executor(
                    self.executor, self._connect_gateway_sync, self.gateway, setting
                )
                break
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                self.status.error_count += 1
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1)
                else:
                    raise

        # Start heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(f"Connected to {self.gateway_name} successfully")

    async def disconnect(self) -> None:
        """Disconnect from gateway."""
        logger.info(f"Disconnecting from {self.gateway_name}...")

        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Disconnect gateway
        if self.gateway:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, self._disconnect_gateway_sync, self.gateway)

        # Stop event engine
        if self.event_engine:
            self.event_engine.stop()
            self.event_engine = None

        # Reset status
        self.status = ConnectionStatus()

        logger.info(f"Disconnected from {self.gateway_name}")

    async def reconnect(
        self,
        credentials: AuthenticationCredentials,
        setting: dict[str, Any],
    ) -> None:
        """
        Reconnect to gateway with retry logic.

        Args:
            credentials: Authentication credentials
            setting: Connection settings
        """
        max_attempts = self.config.max_reconnect_attempts
        delay = self.config.reconnect_interval

        logger.info(
            f"Reconnecting to {self.gateway_name} (max attempts: {max_attempts}, delay: {delay}s)"
        )

        # Disconnect first
        await self.disconnect()

        # Reconnect with retry
        for attempt in range(max_attempts):
            try:
                await self.connect(credentials, setting)
                logger.info("Reconnection successful")
                return
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
                self.status.error_count += 1

                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)
                else:
                    raise

    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop to maintain connection."""
        while True:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                self.status.last_heartbeat = datetime.now(UTC)
                logger.debug(f"Heartbeat: {self.gateway_name}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def is_connected(self) -> bool:
        """
        Check if gateway is connected.

        Returns:
            True if connected, False otherwise
        """
        return (
            self.status.md_connected
            and self.status.td_connected
            and self.status.md_login_status
            and self.status.td_login_status
        )

    def update_status(self, log_msg: str) -> None:
        """
        Update connection status from log messages.

        Args:
            log_msg: Log message from gateway
        """
        # Track connection status from log messages
        if "连接成功" in log_msg or "connected" in log_msg.lower():
            if "行情" in log_msg or "market" in log_msg.lower():
                self.status.md_connected = True
                logger.info("Market data connected")
            elif "交易" in log_msg or "trade" in log_msg.lower():
                self.status.td_connected = True
                logger.info("Trading connected")
        elif "登录成功" in log_msg or "login success" in log_msg.lower():
            if "行情" in log_msg or "market" in log_msg.lower():
                self.status.md_login_status = True
                logger.info("Market data login successful")
            elif "交易" in log_msg or "trade" in log_msg.lower():
                self.status.td_login_status = True
                logger.info("Trading login successful")
        elif "授权验证成功" in log_msg or "auth success" in log_msg.lower():
            self.status.td_auth_status = True
            logger.info("Authentication successful")
        elif "结算" in log_msg or "settlement" in log_msg.lower():
            self.status.settlement_confirmed = True
            logger.info("Settlement confirmed")

    def get_status(self) -> dict[str, Any]:
        """
        Get connection status.

        Returns:
            Dictionary with connection status
        """
        return {
            "is_connected": self.is_connected(),
            "md_connected": self.status.md_connected,
            "md_login": self.status.md_login_status,
            "td_connected": self.status.td_connected,
            "td_login": self.status.td_login_status,
            "td_auth": self.status.td_auth_status,
            "settlement_confirmed": self.status.settlement_confirmed,
            "last_heartbeat": (
                self.status.last_heartbeat.isoformat() if self.status.last_heartbeat else None
            ),
            "error_count": self.status.error_count,
            "last_error": self.status.td_last_error or self.status.md_last_error,
        }
