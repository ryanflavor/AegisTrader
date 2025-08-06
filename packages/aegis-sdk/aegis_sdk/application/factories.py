"""Factory imports for backward compatibility.

This module now serves as a compatibility layer, re-exporting factory
interfaces and implementations from their proper locations in the
hexagonal architecture. New code should import directly from:
- Interfaces: aegis_sdk.ports.factory_ports
- Implementations: aegis_sdk.infrastructure.application_factories

DEPRECATED: This module will be removed in a future version.
Import factories directly from their proper locations instead.
"""

from __future__ import annotations

import warnings

# Import concrete implementations from infrastructure layer
# These are kept here for backward compatibility only
from ..infrastructure.application_factories import (
    DefaultElectionRepositoryFactory,
    DefaultUseCaseFactory,
)

# Import factory interfaces from ports layer
from ..ports.factory_ports import (
    ElectionRepositoryFactory,
    KVStoreFactory,
    UseCaseFactory,
)

# Issue deprecation warning when this module is imported
warnings.warn(
    "aegis_sdk.application.factories is deprecated. "
    "Import factory interfaces from aegis_sdk.ports.factory_ports "
    "and implementations from aegis_sdk.infrastructure.application_factories",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "DefaultElectionRepositoryFactory",
    "DefaultUseCaseFactory",
    "ElectionRepositoryFactory",
    "KVStoreFactory",
    "UseCaseFactory",
]
