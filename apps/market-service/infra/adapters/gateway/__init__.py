"""
Gateway Infrastructure Layer

Production-ready gateway adapters for various trading platforms.
Following DDD principles with clean architecture.
"""

from infra.adapters.gateway.ctp_adapter import (
    CTP_EXCHANGE_MAP,
    CtpConfig,
    CtpGatewayAdapter,
)
from infra.adapters.gateway.gateway_adapter import (
    GatewayAdapter,
    GatewayAdapterConfig,
)
from infra.adapters.gateway.sopt_adapter import (
    SOPT_EXCHANGE_MAP,
    SoptConfig,
    SoptGatewayAdapter,
)

__all__ = [
    # Base gateway adapter
    "GatewayAdapter",
    "GatewayAdapterConfig",
    # CTP adapter
    "CtpGatewayAdapter",
    "CtpConfig",
    "CTP_EXCHANGE_MAP",
    # SOPT adapter
    "SoptGatewayAdapter",
    "SoptConfig",
    "SOPT_EXCHANGE_MAP",
]
