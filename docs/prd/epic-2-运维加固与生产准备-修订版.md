# **Epic 2 \- 运维加固与生产准备 (修订版)**

**目标**: 在核心功能完备后，专注于所有生产环境所需的非功能性需求，例如实现标准化的健康检查、核心监控指标和告警机制，确保服务稳定、可靠地运行。

## **Story 2.1 \- Implement Core Service Health Checks**

**As an** Operator, **I want** a standardized health check endpoint on all services, **so that** I can automatically monitor the health and operational status of each component.

### **Acceptance Criteria**

1. 所有核心服务（Gateways, Validator, Aggregator, Storage）都必须暴露一个名为 health 的RPC端点。
2. 该端点必须返回服务的当前状态（例如 HEALTHY, DEGRADED）及其对关键依赖（NATS, ClickHouse）的连接状态。
3. 对于 SingleActiveService 实例（网关和存储服务），健康检查结果必须明确指出当前实例是否为领导者（leader）。

## **Story 2.2 \- Implement Core Service Metrics**

**As an** Operator, **I want** services to collect and expose key performance metrics, **so that** I can monitor system throughput, latency, and error rates to assess performance and set alerts.

### **Acceptance Criteria**

1. 所有服务必须集成AegisSDK提供的 InMemoryMetrics 收集器。
2. 服务必须自动收集RPC调用和事件处理的标准指标，包括延迟（P50/P95/P99）、吞吐量和错误率。
3. 每个服务必须实现一个名为 metrics 的RPC端点，用于以结构化格式（如JSON）暴露收集到的所有指标。

## **Story 2.3 \- Implement Structured Logging**

**As a** System, **I want** all services to generate structured logs with correlation IDs, **so that** an operator can trace a single request's journey across multiple services for debugging and auditing.

### **Acceptance Criteria**

1. 所有服务都必须使用结构化日志记录器（例如AegisSDK提供的StructuredLogger）。
2. 每一条日志都必须是结构化格式（例如JSON），以便于机器解析。
3. 日志条目中必须包含 trace\_id 或 correlation\_id，以关联跨服务的操作。
4. 服务日志中不得记录任何敏感信息（如密码、API密钥）。
