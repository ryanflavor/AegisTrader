# **10.0 Coding Standards**

* **Python Version**: **3.13+** is required.
* **Type Checking**: **100% type annotation coverage** is mandatory, enforced by mypy with from \_\_future\_\_ import annotations enabled.
* **Entity Specification**: **Pydantic v2** is the sole standard for data entities; @dataclass is forbidden.
* **Enum Usage**: All string constants **must** use domain enums from `aegis_sdk.domain.enums` to prevent hardcoded strings and ensure type safety. Key enums include:
  * `ServiceStatus`: Service operational states (ACTIVE, STANDBY, UNHEALTHY, SHUTDOWN)
  * `StickyActiveStatus`: Leader election states (ACTIVE, STANDBY, ELECTING)
  * `RPCErrorCode`: Standardized RPC error codes (NOT_ACTIVE, SERVICE_UNAVAILABLE, etc.)
* **Async Programming**: All I/O operations **must** use the async/await syntax.
* **Commit Messages**: **Conventional Commits** specification is mandatory for all Git commits.
* **Contract-First**: All core data models **must** be imported from the packages/shared-contracts package.
