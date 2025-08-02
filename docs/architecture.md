# **AegisSDK Enhancement Full Stack Architecture Document (Final Version)**

| Document Status | Final Version |
| :---- | :---- |
| **Version** | 1.0 |
| **Date** | 2025-07-31 |
| **Architect** | Winston (BMad Architect) |

## **1.0 High Level Architecture**

### **1.1 Technical Summary**

This enhancement will introduce a high-availability service registry based on the NATS KV Store to the AegisSDK, and implement a "sticky single-active" RPC pattern designed for critical trading operations. Concurrently, a decoupled monitoring and management system will be built using FastAPI and Next.js. The entire architecture leverages the native capabilities of a NATS cluster to ensure high availability and data consistency, meeting the strict low-latency and high-reliability requirements of a distributed trading system.

### **1.2 Platform & Infrastructure Choice**

* **Platform**: The NATS ecosystem will be fully utilized as the core platform, which avoids introducing external databases or service discovery tools, preserving the lightweight and efficient design philosophy of the AegisSDK.
* **Core Services**:
  * **Messaging & RPC**: Core NATS.
  * **Event/Command Persistence**: NATS JetStream.
  * **Service Registry/Discovery**: NATS KV Store.
* **Deployment**: The NATS cluster will be deployed across multiple nodes for high availability. The management service (FastAPI) and all business services will be designed as independent, redundantly deployable applications.

### **1.3 Repository Structure**

* **Structure**: Monorepo.
* **Rationale**: Adopting a monorepo structure simplifies the management of shared code (like the AegisSDK core and shared Pydantic models) between different services and simplifies the build and deployment processes.

### **1.4 High Level Architecture Diagram**

代码段

graph TD
    subgraph "用户与管理端"
        A\[交易员客户端\]
        B\[监控Web UI\]
    end

    subgraph "核心业务服务 (可冗余部署)"
        C\[行情服务\]
        D\[计算服务\]
        E\[算法服务\]
        F\[交易服务\<br\>\<i\>(粘性单活跃实例/账户)\</i\>\]
    end

    subgraph "核心基础设施"
        G(管理服务\<br\>\<i\>FastAPI\</i\>)
        H(NATS 集群\<br\>\<i\>多节点高可用\</i\>)
        H \--\> H1(Core NATS\<br\>\<i\>RPC & Messaging\</i\>)
        H \--\> H2(JetStream\<br\>\<i\>Events, Commands & KV Store\</i\>)
    end

    A \-- 订阅行情 (Pub/Sub) \--\> C
    A \-- 计算请求 (RPC) \--\> D
    A \-- 算法指令 (RPC) \--\> E
    C \-- 行情广播 (Events) \--\> E
    C \-- 行情广播 (Events) \--\> F
    C \-- 行情广播 (Events) \--\> D
    E \-- 下单 (Sticky RPC) \--\> F
    F \-- 订单/成交回报 (Events) \--\> E
    B \-- HTTP API \--\> G
    G \-- NATS Protocol\<br\>(KV Store Mgmt) \--\> H2
    C \-- 服务注册/心跳 \--\> H2
    D \-- 服务注册/心跳 \--\> H2
    E \-- 服务注册/心跳 \--\> H2
    F \-- 服务注册/心跳 \--\> H2
    A \-.-\> H1
    C \-.-\> H2
    D \-.-\> H1
    E \-.-\> H1 & H2
    F \-.-\> H1 & H2

## **2.0 Tech Stack**

| Category | Technology | Version | Rationale & Purpose |
| :---- | :---- | :---- | :---- |
| **Backend Language** | Python | 3.13+ | Core SDK and management service development language. |
| **Backend Framework** | FastAPI | latest | High-performance for building the management API, with native Pydantic integration. |
| **Frontend Language** | TypeScript | latest | Provides strong type safety, crucial for large, maintainable frontend applications. |
| **Frontend Framework** | Next.js | latest | A production-grade React framework supporting SSR/SSG and API routes, ideal for fast web apps. |
| **UI Components** | Shadcn/ui | latest | A highly customizable and composable UI component set based on Tailwind CSS, offering great flexibility. |
| **CSS Utility** | Tailwind CSS | latest | A utility-first CSS framework that serves as the foundation for Shadcn/ui. |
| **Frontend State** | Zustand | latest | A lightweight and simple state management library, avoiding the complexity of traditional alternatives. |
| **Core Messaging** | NATS & JetStream | 2.9+ | The core system platform, providing RPC, events, commands, and persistence. |
| **Service Registry** | NATS KV Store | N/A | Implements a high-availability service registry without external database dependencies. |
| **Backend Testing** | Pytest | \>=7.0.0 | The standard testing framework for Python, with support for async testing. |
| **Containerization** | Docker | latest | Packages all applications into standardized container images for environmental consistency. |
| **Orchestration** | Kubernetes | latest | Automates deployment, scaling, and management of containerized applications for high availability. |
| **IaC Tool** | Helm Charts | latest | Defines and manages all application deployments on Kubernetes. |
| **CI/CD Pipeline** | GitHub Actions | latest | Automates code integration, testing, building, and deployment pipelines. |

## **3.0 Data Models & Schema Design**

### **3.1 Core Data Models**

* **ServiceDefinition**: Represents the static definition of a service type, managed by administrators and stored in the NATS KV Store.
* **ServiceInstance**: Contains the dynamic information of a running service instance, created on startup and periodically updated via heartbeat.

### **3.2 TypeScript Shared Interfaces**

TypeScript

// Located in packages/shared/src/types.ts
export interface ServiceDefinition {
  serviceName: string;
  owner: string;
  description: string;
  version: string;
  createdAt: string;
  updatedAt: string;
}
export interface ServiceInstance {
  serviceName: string;
  instanceId: string;
  version: string;
  status: 'ACTIVE' | 'UNHEALTHY' | 'STANDBY';
  stickyActiveGroup?: string;
  lastHeartbeat: string;
  metadata?: Record\<string, any\>;
}

## **4.0 API Interface Contracts**

### **4.1 Management Service (FastAPI) \- RESTful API Contract**

YAML

openapi: 3.0.0
info:
  title: "AegisSDK Management API"
  version: "1.0.0"
paths:
  /services:
    get:
      summary: "Get list of all service definitions"
    post:
      summary: "Create a new service definition"
  /services/{serviceName}:
    put:
      summary: "Update an existing service definition"
    delete:
      summary: "Delete a service definition"
  /metrics/live:
    get:
      summary: "Get real-time metrics for all healthy service instances"
components:
  schemas:
    ServiceDefinition: { ... }
    ServiceInstance: { ... }

### **4.2 NATS Internal Messaging Contracts**

* **Order Submission (RPC)**: Uses the subject rpc.trading-service.{accountId}.send\_order with a payload containing fields like symbol, exchange, direction, type, volume, and price.
* **Trade Report (Event)**: Uses the subject events.trading.{accountId}.trade with a payload containing fields like symbol, order\_id, trade\_id, price, and volume.

## **5.0 Source Tree & Project Structure**

Plaintext

/aegis-trading-system/
|-- 📂 apps/
|   |-- 📂 monitor-api/        \# FastAPI Management Backend
|   |-- 📂 monitor-ui/         \# Next.js Monitoring Frontend
|   \`-- 📂 trading-service/    \# (Example) Business Service
|-- 📂 packages/
|   |-- 📂 aegis-sdk/          \# The core AegisSDK
|   \`-- 📂 shared-contracts/   \# Shared Contracts (TypeScript/Pydantic)
|-- 📄 package.json            \# Monorepo root
\`-- 📄 turbo.json              \# Turborepo configuration

## **6.0 Infrastructure & Deployment**

* **Containerization**: **Docker** will be used to package every application into a standalone container image.
* **Orchestration**: **Kubernetes (K8s)** will be used to deploy and manage all containerized services, including the NATS cluster.
* **Infrastructure as Code (IaC)**: **Helm charts** will define and manage all infrastructure resources, as required by Story 0.2.
* **CI/CD**: An automated pipeline using **GitHub Actions** will be established for continuous integration and deployment, as required by Story 0.3.

## **7.0 Component Details**

* **Distributed Communication Core (AegisSDK)**: Encapsulates all NATS interactions, providing simple interfaces for RPC, events, commands, and the sticky single-active pattern.
* **Monitoring & Management System**: A decoupled system composed of the monitor-api and monitor-ui, providing observability and centralized management for the service ecosystem.
* **Core Business Services (High-Level)**:
  * **Market Data Service**: Broadcasts standardized market data to the system.
  * **Calculation Service**: Provides on-demand computational functions.
  * **Algo Service**: Hosts and executes automated trading algorithms.
  * **Trading Service**: Manages the order lifecycle using the sticky single-active pattern.

## **10.0 Coding Standards**

* **Python Version**: **3.13+** is required.
* **Type Checking**: **100% type annotation coverage** is mandatory, enforced by mypy with from \_\_future\_\_ import annotations enabled.
* **Entity Specification**: **Pydantic v2** is the sole standard for data entities; @dataclass is forbidden.
* **Async Programming**: All I/O operations **must** use the async/await syntax.
* **Commit Messages**: **Conventional Commits** specification is mandatory for all Git commits.
* **Contract-First**: All core data models **must** be imported from the packages/shared-contracts package.

## **11.0 Error Handling Strategy**

* **API Error Response**: The RESTful API must return a standardized JSON error structure.
* **Backend Services**: A global exception middleware will be used in FastAPI. Failed event processing will result in messages being sent to a Dead-Letter Queue.
* **Frontend**: A unified data fetching hook will handle API errors and update the UI state accordingly.

## **12.0 Testing Strategy**

* **Methodology**: **Test-Driven Development (TDD)** (Red-Green-Refactor) is the mandatory development workflow.
* **Coverage**: A minimum of **80%** overall test coverage is required, with **100%** coverage for all critical paths and business logic.
* **Integration Testing**: **testcontainers** must be used to test against real dependencies like NATS, forbidding the mocking of core external services.
* **Naming**: Test functions must follow the test\_{functionality}\_{expected\_behavior} convention.

## **13.0 Code Evolution Guidelines**

* **Core Principle**: A single source of truth for all features; file versioning (e.g., service\_v2.py) is strictly forbidden. Code history must be managed by Git.
* **Evolution Patterns**: New functionality should be introduced via **Feature Flags** or the **Strategy Pattern**.
* **Migration Process**: Deprecation of old code must follow a three-step process: ensure backward compatibility, issue deprecation warnings, and remove the code in the next major version.
