# AegisSDK Architecture Diagrams

Visual representations of SDK architecture, message flows, and patterns.

## Table of Contents

1. [System Overview](#system-overview)
2. [Message Flow Patterns](#message-flow-patterns)
3. [Service Discovery Flow](#service-discovery-flow)
4. [Failover Sequence](#failover-sequence)
5. [DDD Layer Architecture](#ddd-layer-architecture)

---

## System Overview

### High-Level Architecture

```mermaid
graph TB
    subgraph "Kubernetes Cluster"
        subgraph "aegis-trader namespace"
            NATS[NATS Server<br/>+ JetStream]
            KV[KV Store<br/>Service Registry]

            subgraph "Services"
                S1[Service A<br/>Instance 1]
                S2[Service A<br/>Instance 2]
                S3[Service B<br/>Leader]
                S4[Service B<br/>Standby]
            end

            subgraph "Clients"
                C1[Client App]
                C2[Monitor API]
            end
        end
    end

    subgraph "Local Development"
        DEV[Developer<br/>Machine]
        PF[Port Forward<br/>:4222]
    end

    NATS --> KV
    S1 --> NATS
    S2 --> NATS
    S3 --> NATS
    S4 --> NATS
    C1 --> NATS
    C2 --> NATS
    DEV --> PF
    PF --> NATS
```

### Component Interaction

```
┌─────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   NATS + JetStream                    │   │
│  │                                                       │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│  │  │   Pub/Sub   │  │     RPC      │  │  KV Store  │  │   │
│  │  │   Events    │  │   Requests   │  │  Registry  │  │   │
│  │  └─────────────┘  └──────────────┘  └────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                            ▲                                 │
│         ┌──────────────────┼──────────────────┐             │
│         │                  │                  │             │
│    ┌────▼─────┐      ┌────▼─────┐      ┌────▼─────┐       │
│    │ Service  │      │ Service  │      │ External │       │
│    │ Pattern  │      │ Pattern  │      │  Client  │       │
│    │  (Load   │      │ (Single  │      │ (Monitor)│       │
│    │ Balanced)│      │  Active) │      │          │       │
│    └──────────┘      └──────────┘      └──────────┘       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Port Forward
                              │ localhost:4222
                              │
                    ┌─────────▼──────────┐
                    │   Developer PC     │
                    │  ┌──────────────┐  │
                    │  │  AegisSDK    │  │
                    │  │  Application │  │
                    │  └──────────────┘  │
                    └────────────────────┘
```

---

## Message Flow Patterns

### 1. Load-Balanced RPC Pattern

```mermaid
sequenceDiagram
    participant Client
    participant NATS
    participant Service1
    participant Service2
    participant Service3

    Note over Service1,Service3: All instances subscribe to same queue group

    Client->>NATS: RPC Request 1<br/>Subject: service.method
    NATS->>Service1: Deliver to Service1<br/>(Round-robin)
    Service1->>NATS: Response 1
    NATS->>Client: Response 1

    Client->>NATS: RPC Request 2<br/>Subject: service.method
    NATS->>Service2: Deliver to Service2<br/>(Round-robin)
    Service2->>NATS: Response 2
    NATS->>Client: Response 2

    Client->>NATS: RPC Request 3<br/>Subject: service.method
    NATS->>Service3: Deliver to Service3<br/>(Round-robin)
    Service3->>NATS: Response 3
    NATS->>Client: Response 3
```

**ASCII Flow:**
```
     Request Distribution (Load-Balanced)

Client ──────► NATS Queue Group ──────► Service Instances
                     │
                     ├──► Request 1 ──► Instance 1
                     ├──► Request 2 ──► Instance 2
                     └──► Request 3 ──► Instance 3

        Automatic round-robin distribution
```

### 2. Single-Active RPC Pattern

```mermaid
sequenceDiagram
    participant Client
    participant NATS
    participant Leader
    participant Standby1
    participant Standby2
    participant KVStore

    Note over Leader: Leader elected via KV Store

    Client->>NATS: RPC Request<br/>Subject: service.exclusive
    NATS->>Leader: Deliver to all instances
    NATS->>Standby1: Deliver to all instances
    NATS->>Standby2: Deliver to all instances

    Standby1->>Client: Error: NOT_ACTIVE
    Standby2->>Client: Error: NOT_ACTIVE
    Leader->>Client: Success Response

    Note over Client: Client retries on NOT_ACTIVE

    Client->>NATS: Retry Request
    NATS->>Leader: Deliver again
    Leader->>Client: Success Response
```

**ASCII Flow:**
```
     Single-Active Pattern with Client Retry

            ┌─────────────────┐
            │   Client App    │
            └────────┬────────┘
                     │ RPC Request
                     ▼
            ┌─────────────────┐
            │      NATS       │
            └────────┬────────┘
                     │ Broadcast to all
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │ LEADER  │  │STANDBY 1│  │STANDBY 2│
  │ Process │  │ Reject  │  │ Reject  │
  └─────────┘  └─────────┘  └─────────┘
       │            │             │
       │            └─────┬───────┘
       │                  │ NOT_ACTIVE
       │                  ▼
       │            ┌─────────┐
       └───────────►│ Client  │
         Success    │ Retries │
                    └─────────┘
```

### 3. Event Publishing Pattern

```mermaid
sequenceDiagram
    participant Publisher
    participant NATS
    participant Sub1_Compete
    participant Sub2_Compete
    participant Sub3_Broadcast
    participant Sub4_Broadcast

    Note over Sub1_Compete,Sub2_Compete: COMPETE mode (queue group)
    Note over Sub3_Broadcast,Sub4_Broadcast: BROADCAST mode (all receive)

    Publisher->>NATS: Publish Event<br/>Subject: orders.created

    NATS->>Sub1_Compete: Deliver to one<br/>(queue group)
    Note over Sub2_Compete: Not delivered<br/>(compete mode)

    NATS->>Sub3_Broadcast: Deliver to all<br/>(broadcast)
    NATS->>Sub4_Broadcast: Deliver to all<br/>(broadcast)
```

**ASCII Flow:**
```
     Event Distribution Patterns

Publisher ──► NATS ──► Subject: orders.created
                │
                ├──► COMPETE Mode (Queue Group)
                │    └──► One of [Sub1, Sub2] receives
                │
                └──► BROADCAST Mode
                     ├──► Sub3 receives
                     └──► Sub4 receives
```

---

## Service Discovery Flow

### Registration and Discovery Sequence

```mermaid
sequenceDiagram
    participant Service
    participant Registry
    participant KVStore
    participant Client
    participant Discovery

    Service->>Registry: Register(name, instance, metadata)
    Registry->>KVStore: PUT /services/{name}/{instance}

    loop Heartbeat
        Service->>Registry: UpdateHealth()
        Registry->>KVStore: UPDATE TTL
    end

    Client->>Discovery: Discover("service-name")
    Discovery->>KVStore: GET /services/service-name/*
    KVStore->>Discovery: List of instances
    Discovery->>Discovery: Apply selection strategy
    Discovery->>Client: Selected instance(s)

    Client->>Service: Direct RPC call
```

**ASCII Representation:**
```
  Service Registration & Discovery Flow

    Service Instance                Client Application
           │                               │
           ▼                               ▼
    ┌──────────────┐              ┌──────────────┐
    │   Register   │              │   Discover   │
    └──────┬───────┘              └───────┬──────┘
           │                               │
           ▼                               ▼
    ┌──────────────────────────────────────┐
    │          KV Store Registry           │
    │                                       │
    │  /services/                          │
    │    ├── echo/                         │
    │    │   ├── instance-1 [metadata]     │
    │    │   ├── instance-2 [metadata]     │
    │    │   └── instance-3 [metadata]     │
    │    └── order/                        │
    │        └── instance-1 [metadata]     │
    └──────────────────────────────────────┘
           ▲                               │
           │                               │
      Heartbeat                     Instance List
       (TTL)                              │
           │                               ▼
    Keep Alive                    Selection Strategy
                                   (Round-Robin/Random)
```

---

## Failover Sequence

### Leader Election and Failover

```mermaid
sequenceDiagram
    participant Instance1
    participant Instance2
    participant Instance3
    participant KVStore
    participant Client

    Note over Instance1,Instance3: Initial State
    Instance1->>KVStore: Acquire Leader Lock
    KVStore->>Instance1: Lock Acquired (Leader)
    Instance2->>KVStore: Try Acquire Lock
    KVStore->>Instance2: Lock Denied (Standby)
    Instance3->>KVStore: Try Acquire Lock
    KVStore->>Instance3: Lock Denied (Standby)

    Note over Instance1: Leader processes requests
    Client->>Instance1: RPC Request
    Instance1->>Client: Success Response

    Note over Instance1: Leader fails
    Instance1->>Instance1: Crash/Network Issue

    Note over KVStore: TTL expires (2 seconds)

    Instance2->>KVStore: Try Acquire Lock
    Instance3->>KVStore: Try Acquire Lock
    KVStore->>Instance2: Lock Acquired (New Leader)
    KVStore->>Instance3: Lock Denied (Standby)

    Note over Instance2: New leader ready
    Client->>Instance2: RPC Request
    Instance2->>Client: Success Response
```

**Failover Timeline:**
```
Time  │ Event
──────┼────────────────────────────────────────
0.0s  │ Instance1 is LEADER
      │ Instance2, Instance3 are STANDBY
      │
1.0s  │ Instance1 sends heartbeat ♥
      │
2.0s  │ Instance1 sends heartbeat ♥
      │
3.0s  │ ✗ Instance1 FAILS (crash/network)
      │
4.0s  │ Heartbeat missed (detection)
      │
5.0s  │ TTL expires in KV Store
      │ Election triggered
      │
5.5s  │ Instance2 attempts lock acquisition
      │ Instance3 attempts lock acquisition
      │
5.8s  │ Instance2 becomes NEW LEADER
      │ Instance3 remains STANDBY
      │
      │ Total Failover Time: 2.8 seconds
```

---

## DDD Layer Architecture

### Hexagonal Architecture Implementation

```mermaid
graph TB
    subgraph "External World"
        USER[User/Client]
        NATS_EXT[NATS Server]
        K8S[Kubernetes]
    end

    subgraph "Application Layer"
        UC[Use Cases]
        SVC[Application Services]
        DTO[DTOs]
    end

    subgraph "Domain Layer (Core)"
        AGG[Aggregates]
        ENT[Entities]
        VO[Value Objects]
        DSVC[Domain Services]
        EVT[Domain Events]
    end

    subgraph "Ports (Interfaces)"
        PORT_IN[Inbound Ports]
        PORT_OUT[Outbound Ports]
    end

    subgraph "Adapters (Infrastructure)"
        REST[REST Adapter]
        NATS_ADAPT[NATS Adapter]
        KV_ADAPT[KV Store Adapter]
        K8S_ADAPT[K8s Discovery Adapter]
    end

    USER --> REST
    REST --> PORT_IN
    PORT_IN --> UC
    UC --> DSVC
    DSVC --> AGG
    AGG --> ENT
    AGG --> VO
    AGG --> EVT

    UC --> PORT_OUT
    PORT_OUT --> NATS_ADAPT
    PORT_OUT --> KV_ADAPT
    PORT_OUT --> K8S_ADAPT

    NATS_ADAPT --> NATS_EXT
    K8S_ADAPT --> K8S
```

**Layer Responsibilities:**

```
┌─────────────────────────────────────────────┐
│            Infrastructure Layer             │
│                                             │
│  • NATS Adapter (messaging)                │
│  • KV Store Adapter (persistence)          │
│  • K8s Discovery (environment)             │
│  • Logging, Metrics, Clock                 │
└─────────────────▲───────────────────────────┘
                  │ implements
┌─────────────────▼───────────────────────────┐
│              Ports Layer                    │
│                                             │
│  • MessageBusPort (interface)              │
│  • ServiceRegistryPort (interface)         │
│  • ServiceDiscoveryPort (interface)        │
│  • MetricsPort (interface)                 │
└─────────────────▲───────────────────────────┘
                  │ uses
┌─────────────────▼───────────────────────────┐
│           Application Layer                 │
│                                             │
│  • Use Cases (RegisterService, etc.)       │
│  • Application Services (orchestration)    │
│  • DTOs (data transfer)                    │
│  • Dependency Injection                    │
└─────────────────▲───────────────────────────┘
                  │ orchestrates
┌─────────────────▼───────────────────────────┐
│             Domain Layer                    │
│                                             │
│  • Aggregates (ServiceAggregate)           │
│  • Entities (ServiceInfo, ElectionInfo)    │
│  • Value Objects (ServiceName, Status)     │
│  • Domain Services (HealthCheck, Election) │
│  • Domain Events (ServiceRegistered)       │
└─────────────────────────────────────────────┘

        Dependencies flow inward only
         Domain has zero dependencies
```

### Data Flow Through Layers

```
  Incoming RPC Request Flow:

     Network                Infrastructure            Application              Domain
        │                         │                         │                    │
   RPC Request ──────► NATS Adapter ──────► RPC Handler ──────► Use Case ──────► Service
        │                         │                         │                    │
        │                    Parse JSON                Validate DTO         Business Logic
        │                         │                         │                    │
        │                    Route to                  Orchestrate           Apply Rules
        │                    Handler                   Dependencies               │
        │                         │                         │                    │
   RPC Response ◄────── Serialize ◄────────── DTO ◄──────────── Result ◄─────────┘
        │                         │                         │                    │

  Service Registration Flow:

     Application              Domain                  Ports              Infrastructure
         │                      │                      │                      │
    Register ──────► ServiceAggregate ──────► RegistryPort ──────► KV Store Adapter
    Command          Create Instance          Interface            NATS KV
         │                      │                      │                      │
         │                 Validate                Abstract            Concrete
         │                 Invariants             Storage            Implementation
         │                      │                      │                      │
    Success ◄────────── Event ◄──────────── Confirmation ◄──────── KV Response
    Response          ServiceRegistered
```

---

## Pattern Decision Tree

```
                    Which Pattern to Use?
                           │
                           ▼
                  ┌─────────────────┐
                  │ Need to provide │
                  │    a service?   │
                  └────────┬────────┘
                     Yes │ │ No
                ┌────────┘ └────────┐
                ▼                    ▼
        ┌─────────────┐      ┌─────────────┐
        │  Stateful?  │      │  External   │
        └──────┬──────┘      │   Client    │
          Yes │ │ No         │  (Monitor)  │
      ┌───────┘ └───────┐    └─────────────┘
      ▼                 ▼
┌─────────────┐   ┌─────────────┐
│   Single    │   │    Load     │
│   Active    │   │  Balanced   │
│  Service    │   │   Service   │
└─────────────┘   └─────────────┘
      │                 │
      ▼                 ▼
 Only leader      All instances
 processes          process
  requests          requests
```

---

## Monitoring and Observability

```
     Service Metrics Flow

Service ──► Metrics ──► Metadata ──► Registry ──► Monitor
Instance    Collector   Enrichment    (KV)        API/UI
   │           │            │           │            │
   │      Collect      Aggregate    Store in     Query &
   │      - Latency    - Health     Instance     Display
   │      - Errors     - Grade      Metadata
   │      - Count      - Score
   │
   └──► Performance Tracking
        - Request Rate: 1234 req/min
        - Error Rate: 0.12%
        - P50 Latency: 12ms
        - P99 Latency: 145ms
        - Health Score: 98.5/100
```

---

## Quick Reference Diagrams

### Service Lifecycle
```
 INIT ──► STARTING ──► RUNNING ──► STOPPING ──► STOPPED
             │            │            │
             ▼            ▼            ▼
         Register    Heartbeat    Deregister
          in KV       Active        from KV
```

### Message Types
```
RPC:      Request ──► Response (point-to-point)
Event:    Publish ──► Subscribe (one-to-many)
Command:  Send ──► Execute (directed action)
Stream:   Produce ──► Consume (ordered sequence)
```

### Selection Strategies
```
Round-Robin:  1→2→3→1→2→3 (sequential)
Random:       2→1→3→3→1→2 (random)
Least-Loaded: →[least work]→ (by metrics)
```

---

These diagrams provide a comprehensive view of AegisSDK's architecture and message flows. Use them to understand how components interact and how to design your services effectively.
