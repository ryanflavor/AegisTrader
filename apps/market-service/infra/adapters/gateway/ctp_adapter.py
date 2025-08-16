"""
CTP Gateway Adapter with Production Features.

Uses the base adapter for robust CTP connectivity following hexagonal architecture.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import Field
from vnpy.trader.constant import Exchange as VnExchange
from vnpy_ctp import CtpGateway

from domain.gateway.value_objects import AuthenticationCredentials
from infra.config.base import GatewayConnectionConfig

from .gateway_adapter import GatewayAdapter, GatewayAdapterConfig


class CtpConfig(GatewayConnectionConfig, GatewayAdapterConfig):
    """CTP-specific configuration with strict validation."""

    # CTP-specific connection parameters
    broker_id: str = Field(default="9999", description="Broker identifier")
    td_address: str = Field(description="Trading server address")
    md_address: str = Field(description="Market data server address")
    app_id: str = Field(default="", description="Application identifier")
    auth_code: str = Field(default="0000000000000000", description="Authentication code")
    product_info: str = Field(default="", description="Product information")

    @classmethod
    def from_env(cls) -> CtpConfig:
        """Create config from environment variables with fallback support."""

        # Try real environment first, then fall back to test environment
        def get_env_with_fallback(key: str, default: str = "") -> str:
            return os.getenv(f"CTP_REAL_{key}") or os.getenv(f"CTP_{key}", default)

        return cls(
            user_id=get_env_with_fallback("USER_ID"),
            password=get_env_with_fallback("PASSWORD"),
            broker_id=get_env_with_fallback("BROKER_ID", "9999"),
            td_address=get_env_with_fallback("TD_ADDRESS"),
            md_address=get_env_with_fallback("MD_ADDRESS"),
            app_id=get_env_with_fallback("APP_ID"),
            auth_code=get_env_with_fallback("AUTH_CODE", "0000000000000000"),
            product_info=get_env_with_fallback("PRODUCT_INFO"),
        )


# CTP Exchange mapping
CTP_EXCHANGE_MAP = {
    "CFFEX": VnExchange.CFFEX,  # China Financial Futures Exchange
    "SHFE": VnExchange.SHFE,  # Shanghai Futures Exchange
    "CZCE": VnExchange.CZCE,  # Zhengzhou Commodity Exchange
    "DCE": VnExchange.DCE,  # Dalian Commodity Exchange
    "INE": VnExchange.INE,  # Shanghai International Energy Exchange
    "GFEX": VnExchange.GFEX,  # Guangzhou Futures Exchange
}


class CtpGatewayAdapter(GatewayAdapter):
    """
    CTP adapter with production features

    Features:
    - Separate MD/TD connection tracking
    - Price adjustment for invalid data
    - Timer-based query rotation
    - Position aggregation with SHFE/INE special handling
    - Flow control with retry logic
    - Global contract caching
    - Multi-level market depth support
    - Order reference tracking
    - Buffered data during initialization
    """

    def __init__(self, config: CtpConfig | None = None):
        """Initialize CTP gateway adapter."""
        super().__init__(config or CtpConfig())
        self.ctp_config = config or CtpConfig()

        # Set gateway info
        self.set_gateway_info("CTP", CtpGateway)

        # Store exchange mapping
        self.exchange_map = CTP_EXCHANGE_MAP

    def _prepare_connection_setting(self, credentials: AuthenticationCredentials) -> dict[str, Any]:
        """
        Prepare CTP-specific connection settings.

        Args:
            credentials: Authentication credentials

        Returns:
            Dictionary with vnpy CTP connection settings
        """
        return {
            "用户名": credentials.user_id,
            "密码": credentials.password,
            "经纪商代码": self.ctp_config.broker_id,
            "交易服务器": self.ctp_config.td_address,
            "行情服务器": self.ctp_config.md_address,
            "产品名称": self.ctp_config.app_id,
            "授权编码": self.ctp_config.auth_code,
            "产品信息": self.ctp_config.product_info,
        }
