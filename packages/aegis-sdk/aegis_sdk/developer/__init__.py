"""Developer experience tools for AegisSDK.

DEPRECATED: This module has been moved to aegis-sdk-dev package.
Please install and use aegis-sdk-dev instead:
    pip install aegis-sdk-dev
    from aegis_sdk_dev import ...

This module will be removed in a future version.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "aegis_sdk.developer is deprecated. Please use aegis-sdk-dev package instead.",
    DeprecationWarning,
    stacklevel=2,
)

from aegis_sdk.developer.config_helper import (
    K8sNATSConfig,
    SDKConfig,
    create_external_client,
    create_service,
    discover_k8s_config,
    quick_setup,
)
from aegis_sdk.developer.environment import (
    Environment,
    detect_environment,
    is_kubernetes_available,
)

__all__ = [
    "Environment",
    "K8sNATSConfig",
    "SDKConfig",
    "create_external_client",
    "create_service",
    "detect_environment",
    "discover_k8s_config",
    "is_kubernetes_available",
    "quick_setup",
]
