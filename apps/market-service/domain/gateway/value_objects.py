"""
Gateway domain value objects
Following DDD patterns with Pydantic v2
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class GatewayId(str):
    """Value object for Gateway ID"""

    def __new__(cls, value: str):
        if not value or not value.strip():
            raise ValueError("GatewayId cannot be empty")
        return super().__new__(cls, value)


class GatewayType(str, Enum):
    """Enumeration of supported gateway types"""

    CTP = "CTP"  # CTP for Chinese futures
    SOPT = "SOPT"  # SOPT for Chinese options
    IB = "IB"  # Interactive Brokers
    BINANCE = "BINANCE"  # Binance crypto
    OKEX = "OKEX"  # OKEx crypto


class ConnectionState(str, Enum):
    """Connection state enumeration"""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class Symbol(str):
    """Value object for trading symbol"""

    def __new__(cls, value: str):
        if not value or not value.strip():
            raise ValueError("Symbol cannot be empty")
        return super().__new__(cls, value.upper())


class Exchange(str, Enum):
    """Exchange enumeration"""

    SHFE = "SHFE"  # Shanghai Futures Exchange
    DCE = "DCE"  # Dalian Commodity Exchange
    CZCE = "CZCE"  # Zhengzhou Commodity Exchange
    CFFEX = "CFFEX"  # China Financial Futures Exchange
    INE = "INE"  # Shanghai International Energy Exchange
    SSE = "SSE"  # Shanghai Stock Exchange
    SZSE = "SZSE"  # Shenzhen Stock Exchange

    @classmethod
    def from_ctp(cls, ctp_exchange: str) -> Exchange:
        """Convert CTP exchange code to Exchange enum"""
        mapping = {
            "SHFE": cls.SHFE,
            "DCE": cls.DCE,
            "CZCE": cls.CZCE,
            "CFFEX": cls.CFFEX,
            "INE": cls.INE,
            "SSE": cls.SSE,
            "SZSE": cls.SZSE,
        }
        exchange = mapping.get(ctp_exchange.upper())
        if not exchange:
            raise ValueError(f"Unknown CTP exchange: {ctp_exchange}")
        return exchange


class HeartbeatConfig(BaseModel):
    """Configuration for heartbeat mechanism"""

    interval: int = Field(default=30, description="Heartbeat interval in seconds")
    timeout: int = Field(default=60, description="Heartbeat timeout in seconds")
    enabled: bool = Field(default=True, description="Whether heartbeat is enabled")

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Heartbeat interval must be positive")
        if v > 300:
            raise ValueError("Heartbeat interval cannot exceed 300 seconds")
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int, info) -> int:
        if v <= 0:
            raise ValueError("Heartbeat timeout must be positive")
        # Timeout should be at least 2x interval
        interval = info.data.get("interval", 30)
        if v < interval * 2:
            raise ValueError("Heartbeat timeout should be at least 2x the interval")
        return v


class ConnectionConfig(BaseModel):
    """Configuration for connection management"""

    reconnect_delay: int = Field(default=5, description="Initial reconnect delay in seconds")
    max_reconnect_attempts: int = Field(default=10, description="Maximum reconnection attempts")
    connection_timeout: int = Field(default=30, description="Connection timeout in seconds")
    heartbeat_config: HeartbeatConfig = Field(default_factory=HeartbeatConfig)

    @field_validator("reconnect_delay")
    @classmethod
    def validate_reconnect_delay(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Reconnect delay must be positive")
        return v

    @field_validator("max_reconnect_attempts")
    @classmethod
    def validate_max_attempts(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Max reconnect attempts cannot be negative")
        if v > 100:
            raise ValueError("Max reconnect attempts cannot exceed 100")
        return v


class GatewayConfig(BaseModel):
    """Complete gateway configuration"""

    gateway_id: str = Field(description="Unique gateway identifier")
    gateway_type: GatewayType = Field(description="Type of gateway")
    heartbeat_interval: int = Field(default=30, description="Heartbeat interval in seconds")
    reconnect_delay: int = Field(default=5, description="Reconnection delay in seconds")
    max_reconnect_attempts: int = Field(default=10, description="Maximum reconnection attempts")
    failover_timeout: int | None = Field(default=2, description="Failover timeout in seconds")
    heartbeat_config: HeartbeatConfig | None = Field(default_factory=HeartbeatConfig)

    def to_connection_config(self) -> ConnectionConfig:
        """Convert to ConnectionConfig"""
        return ConnectionConfig(
            reconnect_delay=self.reconnect_delay,
            max_reconnect_attempts=self.max_reconnect_attempts,
            connection_timeout=30,  # Default
            heartbeat_config=self.heartbeat_config
            or HeartbeatConfig(interval=self.heartbeat_interval),
        )


class AuthenticationCredentials(BaseModel):
    """Authentication credentials for gateway connection"""

    user_id: str = Field(description="User ID")
    password: str = Field(description="Password")
    broker_id: str | None = Field(default=None, description="Broker ID")
    app_id: str | None = Field(default=None, description="Application ID")
    auth_code: str | None = Field(default=None, description="Authentication code")

    model_config = {
        # Prevent credentials from being logged in serialization
        "json_schema_extra": {"sensitive_fields": ["password", "auth_code"]}
    }
