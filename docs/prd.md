# **Market Service 产品需求文档 (PRD)**

## **目标与背景**

### **目标**

* 构建一个高性能、高可用、可扩展的实时行情服务。
* 支持多种市场数据源接入（首先是CTP期货和SOPT期权）。
* 实现毫秒级的数据处理延迟（P99延迟 \< 1ms）。
* 支持高吞吐量的数据处理能力（\> 50,000 TPS）。
* 通过实时验证、异常检测和质量监控，确保最高标准的数据质量。
* 将验证后的Tick数据发布到PubSub，并将分钟K线数据高效地存储到ClickHouse。

### **背景简介**

本项目旨在构建一个新的“Market Service”，它将成为AegisTrader生态系统中的核心服务。该服务的核心业务价值在于提供实时、准确的市场数据，这是整个交易决策系统的生命线。

该服务将基于已有的AegisSDK框架进行开发，充分利用其提供的六边形架构、高性能NATS消息传递以及高可用服务模式（如SingleActiveService）。整个设计遵循领域驱动设计（DDD）的最佳实践，将复杂的数据处理逻辑清晰地划分到独立的限界上下文中，以确保系统的长期可维护性和可扩展性。

### **变更日志**

| 日期 | 版本 | 描述 | 作者 |
| :---- | :---- | :---- | :---- |
| 2025-08-11 | 1.0 | 基于DDD设计文档创建初始草案 | John (PM) |

---

## **需求 (修订版 \- MVP焦点)**

### **功能性需求 (Functional Requirements)**

#### **MVP 核心需求**

* **FR1**: 系统必须能接收来自CTP（期货）和SOPT（股票期权）数据源的实时Tick行情数据。
* **FR2**: 系统必须根据核心规则对所有传入的Tick数据进行验证，包括数据完整性、时序一致性（时间戳单调递增）、价格合理性（在涨跌停范围内）以及成交量逻辑（单调递增）。
* **FR3**: 系统必须能够识别并拒绝无效的Tick数据，并为此生成TickRejected领域事件。
* **FR4**: 验证通过的Tick数据 (ValidatedTick) 必须被发布到NATS JetStream消息队列中，供下游服务消费。
* **FR5**: 系统必须能够将验证后的Tick数据聚合为一分钟的OHLCV K线 (MarketBar)。
* **FR6**: 系统必须将生成的MarketBar数据持久化存储到ClickHouse数据库中。
* **FR7**: 系统必须管理与行情数据源的连接，包括自动认证和在连接断开时的自动重连机制。
* **FR10**: 系统必须能够管理交易合约的订阅列表。

#### **Post-MVP (第二阶段) 规划**

* **FR8**: 实现基于DataQualityMonitor聚合的实时数据流质量评分和监控。
* **FR9**: 实现基于统计学方法（如Z-Score）的市场价格异常自动检测。

### **非功能性需求 (Non-Functional Requirements)**

#### **MVP 目标**

* **NFR1 (性能-延迟)**: **目标** P99延迟小于10毫秒，架构设计应具备优化到亚毫秒级的能力。
* **NFR2 (性能-吞吐量)**: **目标** 稳定处理每秒10,000笔Tick数据，架构设计应支持水平扩展以达到50,000+ TPS。
* **NFR3 (可用性)**: **目标** 达到99.9%的可用性，并实现关键服务的自动故障转移。架构应支持未来达到99.95%的更高目标。

#### **长期遵循**

* **NFR4 (数据一致性)**: 在单个MarketDataStream聚合的边界内，数据必须是强一致的。跨聚合操作和历史数据存储采用最终一致性。
* **NFR5 (数据完整性)**: 一旦生成的MarketBar（K线）被存储，它就必须是不可变的。
* **NFR6 (可伸缩性)**: 无状态的处理组件（如验证服务）必须支持水平扩展。
* **NFR7 (可观测性)**: 系统必须提供结构化的日志和核心性能指标。

---

## **Epics**

1. **Epic 1 \- 核心数据流水线与多网关集成**: 一次性建立完整的端到端数据处理流水线，并同时实现CTP和SOPT两个网关的集成。
2. **Epic 2 \- 运维加固与生产准备**: 在核心功能完备后，专注于所有生产环境所需的非功能性需求，例如实现标准化的健康检查、核心监控指标和告警机制。

---

## **Epic 1 \- 核心数据流水线与多网关集成 (修订版)**

**目标**: 一次性建立完整的端到端数据处理流水线，并**同时实现CTP和SOPT两个网关的集成**。这个Epic完成后，系统将具备处理两种数据源的全部核心能力，并为后续的运维加固工作（Epic 2）打下坚实的基础。

### **Story 1.1 \- Project Scaffolding and Core Dependencies**

**As a** System, **I want** to initialize a new service project using the aegis-sdk-dev toolkit and install core dependencies, **so that** developers have a consistent and ready-to-use codebase foundation.

#### **Acceptance Criteria**

1. 使用 aegis-bootstrap 命令成功创建一个新的 market-service 项目。
2. 项目目录结构必须符合 aegis-sdk-dev 定义的企业级DDD模板标准。
3. 核心依赖（aegis-sdk, clickhouse-driver, vnpy）已添加到 pyproject.toml 文件中。
4. 项目的虚拟环境已成功创建，并且所有依赖都已安装。
5. 实现一个基础的健康检查RPC端点 (health\_check)，以验证服务能够成功启动并响应请求。

### **Story 1.2 \- Generic Gateway Service and CTP Adapter**

**As a** System, **I want** to implement a generic, high-availability gateway service using the SingleActiveService pattern and create the specific adapter for the CTP data source, **so that** a robust foundation for connecting to multiple exchanges is established.

#### **Acceptance Criteria**

1. 创建一个 market-gateway 服务，该服务必须继承自 AegisSDK 的 SingleActiveService。
2. 服务内包含通用的连接管理逻辑（连接、断开、重连）。
3. 实现一个专门用于CTP的**适配器 (Adapter)**，负责处理CTP协议的认证和连接细节。
4. 服务能够通过CTP适配器成功连接到CTP数据源并维持心跳。

### **Story 1.3 \- SOPT Adapter and Anti-Corruption Layer**

**As a** System, **I want** to implement the SOPT adapter and an Anti-Corruption Layer (ACL) within the existing gateway service, **so that** SOPT data can be seamlessly integrated and translated into our domain model.

#### **Acceptance Criteria**

1. 在 market-gateway 服务中实现一个专门用于SOPT的**适配器 (Adapter)**。
2. 在 crossdomain 层中创建一个**防腐层 (ACL)**，负责将SOPT的特定数据格式准确地转换为我们内部统一的 MarketTick 领域模型。
3. 服务能够通过SOPT适配器成功连接到SOPT数据源。
4. 现在，market-gateway 服务可以通过配置选择，连接到CTP或SOPT数据源。

### **Story 1.4 \- Unified Tick Validation Service**

**As a** System, **I want** to create a validation service that receives MarketTick objects from any gateway and applies core validation rules, **so that** a single, scalable point of quality control is established for all data sources.

#### **Acceptance Criteria**

1. 创建一个无状态、可水平扩展的 market-validator 服务。
2. 服务提供一个RPC端点，用于接收来自任何网关的、已经过ACL转换的 MarketTick 对象。
3. 服务必须对 MarketTick 执行核心验证规则（时间戳单调递增、成交量单调递增、价格在涨跌停限制内）。
4. 验证通过的Tick被转换为ValidatedTick值对象，验证失败的则被拒绝并记录。

### **Story 1.5 \- Multi-Source Event Publishing**

**As a** System, **I want** to publish validated tick data from different sources to distinct event streams on NATS JetStream, **so that** downstream consumers can selectively subscribe to the data they need.

#### **Acceptance Criteria**

1. market-validator 服务在成功验证Tick后，必须创建一个 ValidatedTick 领域事件。
2. 来自CTP的事件被发布到 events.market.tick.ctp 主题。
3. 来自SOPT的事件被发布到 events.market.tick.sopt 主题。
4. 所有事件都以持久化模式发布到JetStream。

### **Story 1.6 \- Unified Bar Aggregation and Storage**

**As a** System, **I want** to implement unified aggregation and storage services that can process events from both CTP and SOPT data streams, **so that** all market data is aggregated and stored consistently.

#### **Acceptance Criteria**

1. market-aggregator 服务必须能同时订阅 events.market.tick.ctp 和 events.market.tick.sopt 两个主题。
2. 服务能为来自不同数据源的合约正确地生成一分钟K线 (MarketBar)。
3. market-storage 服务能接收所有来源的K线数据。
4. 服务能将K线数据正确地存入ClickHouse，并能通过字段区分其原始数据源（CTP或SOPT）。

---

## **Epic 2 \- 运维加固与生产准备 (修订版)**

**目标**: 在核心功能完备后，专注于所有生产环境所需的非功能性需求，例如实现标准化的健康检查、核心监控指标和告警机制，确保服务稳定、可靠地运行。

### **Story 2.1 \- Implement Core Service Health Checks**

**As an** Operator, **I want** a standardized health check endpoint on all services, **so that** I can automatically monitor the health and operational status of each component.

#### **Acceptance Criteria**

1. 所有核心服务（Gateways, Validator, Aggregator, Storage）都必须暴露一个名为 health 的RPC端点。
2. 该端点必须返回服务的当前状态（例如 HEALTHY, DEGRADED）及其对关键依赖（NATS, ClickHouse）的连接状态。
3. 对于 SingleActiveService 实例（网关和存储服务），健康检查结果必须明确指出当前实例是否为领导者（leader）。

### **Story 2.2 \- Implement Core Service Metrics**

**As an** Operator, **I want** services to collect and expose key performance metrics, **so that** I can monitor system throughput, latency, and error rates to assess performance and set alerts.

#### **Acceptance Criteria**

1. 所有服务必须集成AegisSDK提供的 InMemoryMetrics 收集器。
2. 服务必须自动收集RPC调用和事件处理的标准指标，包括延迟（P50/P95/P99）、吞吐量和错误率。
3. 每个服务必须实现一个名为 metrics 的RPC端点，用于以结构化格式（如JSON）暴露收集到的所有指标。

### **Story 2.3 \- Implement Structured Logging**

**As a** System, **I want** all services to generate structured logs with correlation IDs, **so that** an operator can trace a single request's journey across multiple services for debugging and auditing.

#### **Acceptance Criteria**

1. 所有服务都必须使用结构化日志记录器（例如AegisSDK提供的StructuredLogger）。
2. 每一条日志都必须是结构化格式（例如JSON），以便于机器解析。
3. 日志条目中必须包含 trace\_id 或 correlation\_id，以关联跨服务的操作。
4. 服务日志中不得记录任何敏感信息（如密码、API密钥）。
