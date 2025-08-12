# **Tech Stack Alignment**

The enhancement will adopt the established technology stack of the Aegis platform.

| Category | Current Technology | Version | Usage in Enhancement | Notes |
| :---- | :---- | :---- | :---- | :---- |
| **Language** | Python | 3.13+ | Core implementation language | Adheres to platform standard |
| **Framework** | AegisSDK | 4.1.0 (assumed) | Service lifecycle, messaging, HA | Core runtime for all services |
| **Messaging** | NATS JetStream | 2.9+ | Events, Commands, KV Store | Central nervous system for all communication |
| **Database** | ClickHouse | Cluster | Historical data persistence | Chosen for time-series performance |
| **Cache** | NATS KV Store | \- | Real-time data, K-line cache | Unified tech stack, leverages NATS |
| **API Style** | RPC over NATS | \- | Internal service communication | AegisSDK's native communication pattern |
| **Testing** | pytest | \- | Unit and Integration Testing | Standard from aegis-sdk-dev template |
| **Deployment** | Docker / K8s / Helm | \- | Containerization and Orchestration | Standard platform deployment method |
