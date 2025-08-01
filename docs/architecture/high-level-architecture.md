# **1.0 High Level Architecture**

## **1.1 Technical Summary**

This enhancement will introduce a high-availability service registry based on the NATS KV Store to the AegisSDK, and implement a "sticky single-active" RPC pattern designed for critical trading operations. Concurrently, a decoupled monitoring and management system will be built using FastAPI and Next.js. The entire architecture leverages the native capabilities of a NATS cluster to ensure high availability and data consistency, meeting the strict low-latency and high-reliability requirements of a distributed trading system.

## **1.2 Platform & Infrastructure Choice**

* **Platform**: The NATS ecosystem will be fully utilized as the core platform, which avoids introducing external databases or service discovery tools, preserving the lightweight and efficient design philosophy of the AegisSDK.  
* **Core Services**:  
  * **Messaging & RPC**: Core NATS.  
  * **Event/Command Persistence**: NATS JetStream.  
  * **Service Registry/Discovery**: NATS KV Store.  
* **Deployment**: The NATS cluster will be deployed across multiple nodes for high availability. The management service (FastAPI) and all business services will be designed as independent, redundantly deployable applications.

## **1.3 Repository Structure**

* **Structure**: Monorepo.  
* **Rationale**: Adopting a monorepo structure simplifies the management of shared code (like the AegisSDK core and shared Pydantic models) between different services and simplifies the build and deployment processes.

## **1.4 High Level Architecture Diagram**

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
