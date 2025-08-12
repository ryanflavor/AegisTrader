# **Epic 1 \- 核心数据流水线与多网关集成 (修订版)**

**目标**: 一次性建立完整的端到端数据处理流水线，并**同时实现CTP和SOPT两个网关的集成**。这个Epic完成后，系统将具备处理两种数据源的全部核心能力，并为后续的运维加固工作（Epic 2）打下坚实的基础。

## **Story 1.1 \- Project Scaffolding and Core Dependencies**

**As a** System, **I want** to initialize a new service project using the aegis-sdk-dev toolkit and install core dependencies, **so that** developers have a consistent and ready-to-use codebase foundation.

### **Acceptance Criteria**

1. 使用 aegis-bootstrap 命令成功创建一个新的 market-service 项目。  
2. 项目目录结构必须符合 aegis-sdk-dev 定义的企业级DDD模板标准。  
3. 核心依赖（aegis-sdk, clickhouse-driver, vnpy）已添加到 pyproject.toml 文件中。  
4. 项目的虚拟环境已成功创建，并且所有依赖都已安装。  
5. 实现一个基础的健康检查RPC端点 (health\_check)，以验证服务能够成功启动并响应请求。

## **Story 1.2 \- Generic Gateway Service and CTP Adapter**

**As a** System, **I want** to implement a generic, high-availability gateway service using the SingleActiveService pattern and create the specific adapter for the CTP data source, **so that** a robust foundation for connecting to multiple exchanges is established.

### **Acceptance Criteria**

1. 创建一个 market-gateway 服务，该服务必须继承自 AegisSDK 的 SingleActiveService。  
2. 服务内包含通用的连接管理逻辑（连接、断开、重连）。  
3. 实现一个专门用于CTP的**适配器 (Adapter)**，负责处理CTP协议的认证和连接细节。  
4. 服务能够通过CTP适配器成功连接到CTP数据源并维持心跳。

## **Story 1.3 \- SOPT Adapter and Anti-Corruption Layer**

**As a** System, **I want** to implement the SOPT adapter and an Anti-Corruption Layer (ACL) within the existing gateway service, **so that** SOPT data can be seamlessly integrated and translated into our domain model.

### **Acceptance Criteria**

1. 在 market-gateway 服务中实现一个专门用于SOPT的**适配器 (Adapter)**。  
2. 在 crossdomain 层中创建一个**防腐层 (ACL)**，负责将SOPT的特定数据格式准确地转换为我们内部统一的 MarketTick 领域模型。  
3. 服务能够通过SOPT适配器成功连接到SOPT数据源。  
4. 现在，market-gateway 服务可以通过配置选择，连接到CTP或SOPT数据源。

## **Story 1.4 \- Unified Tick Validation Service**

**As a** System, **I want** to create a validation service that receives MarketTick objects from any gateway and applies core validation rules, **so that** a single, scalable point of quality control is established for all data sources.

### **Acceptance Criteria**

1. 创建一个无状态、可水平扩展的 market-validator 服务。  
2. 服务提供一个RPC端点，用于接收来自任何网关的、已经过ACL转换的 MarketTick 对象。  
3. 服务必须对 MarketTick 执行核心验证规则（时间戳单调递增、成交量单调递增、价格在涨跌停限制内）。  
4. 验证通过的Tick被转换为ValidatedTick值对象，验证失败的则被拒绝并记录。

## **Story 1.5 \- Multi-Source Event Publishing**

**As a** System, **I want** to publish validated tick data from different sources to distinct event streams on NATS JetStream, **so that** downstream consumers can selectively subscribe to the data they need.

### **Acceptance Criteria**

1. market-validator 服务在成功验证Tick后，必须创建一个 ValidatedTick 领域事件。  
2. 来自CTP的事件被发布到 events.market.tick.ctp 主题。  
3. 来自SOPT的事件被发布到 events.market.tick.sopt 主题。  
4. 所有事件都以持久化模式发布到JetStream。

## **Story 1.6 \- Unified Bar Aggregation and Storage**

**As a** System, **I want** to implement unified aggregation and storage services that can process events from both CTP and SOPT data streams, **so that** all market data is aggregated and stored consistently.

### **Acceptance Criteria**

1. market-aggregator 服务必须能同时订阅 events.market.tick.ctp 和 events.market.tick.sopt 两个主题。  
2. 服务能为来自不同数据源的合约正确地生成一分钟K线 (MarketBar)。  
3. market-storage 服务能接收所有来源的K线数据。  
4. 服务能将K线数据正确地存入ClickHouse，并能通过字段区分其原始数据源（CTP或SOPT）。

---
