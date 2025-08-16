"""
SOPT Gateway Adapter for Stock & Options Trading
Uses the base adapter for robust SOPT connectivity
"""

from __future__ import annotations

from typing import Any

from vnpy.trader.constant import Exchange as VnExchange
from vnpy_sopt import SoptGateway

from domain.gateway.value_objects import AuthenticationCredentials
from infra.adapters.gateway.gateway_adapter import (
    GatewayAdapter,
    GatewayAdapterConfig,
)


class SoptConfig(GatewayAdapterConfig):
    """SOPT-specific configuration"""

    # SOPT connection parameters
    user_id: str = ""
    password: str = ""
    broker_id: str = "9999"
    td_address: str = ""
    md_address: str = ""
    app_id: str = ""
    auth_code: str = "0000000000000000"
    product_info: str = ""

    @classmethod
    def from_env(cls) -> SoptConfig:
        """Create config from environment variables"""
        import os

        return cls(
            user_id=os.getenv("SOPT_USER_ID", ""),
            password=os.getenv("SOPT_PASSWORD", ""),
            broker_id=os.getenv("SOPT_BROKER_ID", "9999"),
            td_address=os.getenv("SOPT_TD_ADDRESS", ""),
            md_address=os.getenv("SOPT_MD_ADDRESS", ""),
            app_id=os.getenv("SOPT_APP_ID", ""),
            auth_code=os.getenv("SOPT_AUTH_CODE", "0000000000000000"),
            product_info=os.getenv("SOPT_PRODUCT_INFO", ""),
        )


# SOPT Exchange mapping (Stock & Options)
SOPT_EXCHANGE_MAP = {
    "SSE": VnExchange.SSE,  # Shanghai Stock Exchange
    "SZSE": VnExchange.SZSE,  # Shenzhen Stock Exchange
}


class SoptGatewayAdapter(GatewayAdapter):
    """
    SOPT adapter for stock and options trading

    Features:
    - Stock and ETF options support
    - Separate MD/TD connection tracking
    - Price adjustment for invalid data
    - Timer-based query rotation
    - Position aggregation
    - Flow control with retry logic
    - Global contract caching
    - Multi-level market depth support
    - Order reference tracking
    - Trading status tracking (continuous, auction, etc.)
    """

    def __init__(self, config: SoptConfig | None = None):
        """Initialize SOPT gateway adapter."""
        super().__init__(config or SoptConfig())
        self.sopt_config = config or SoptConfig()

        # Set gateway info
        self.set_gateway_info("SOPT", SoptGateway)

        # Store exchange mapping
        self.exchange_map = SOPT_EXCHANGE_MAP

    def _prepare_connection_setting(self, credentials: AuthenticationCredentials) -> dict[str, Any]:
        """
        Prepare SOPT-specific connection settings.

        Args:
            credentials: Authentication credentials

        Returns:
            Dictionary with vnpy SOPT connection settings
        """
        return {
            "用户名": credentials.user_id,
            "密码": credentials.password,
            "经纪商代码": self.sopt_config.broker_id,
            "交易服务器": self.sopt_config.td_address,
            "行情服务器": self.sopt_config.md_address,
            "产品名称": self.sopt_config.app_id,
            "授权编码": self.sopt_config.auth_code,
            "产品信息": self.sopt_config.product_info,
        }
