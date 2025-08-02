# **7.0 Component Details**

* **Distributed Communication Core (AegisSDK)**: Encapsulates all NATS interactions, providing simple interfaces for RPC, events, commands, and the sticky single-active pattern.
* **Monitoring & Management System**: A decoupled system composed of the monitor-api and monitor-ui, providing observability and centralized management for the service ecosystem.
* **Core Business Services (High-Level)**:
  * **Market Data Service**: Broadcasts standardized market data to the system.
  * **Calculation Service**: Provides on-demand computational functions.
  * **Algo Service**: Hosts and executes automated trading algorithms.
  * **Trading Service**: Manages the order lifecycle using the sticky single-active pattern.
