# **Component Architecture**

The market-service will be built as a **single, unified application** that internally adheres to a logical, layered DDD architecture.

* **Domain Layer**: The core of the application. It contains the business logic, aggregates (MarketDataStream), entities, and value objects that are free from any infrastructure concerns.  
* **Application Layer**: Orchestrates the domain layer to perform application-specific tasks. It defines the use cases (e.g., "process a market tick") but does not contain business logic itself.  
* **Infrastructure Layer**: Contains the implementation details for external concerns, such as the NATS adapter for messaging, the ClickHouse repository for persistence, and adapters for the vnpy gateways.  
* **Cross-domain Layer**: Provides the Anti-Corruption Layer (ACL) to translate data from external sources (like CTP/SOPT) into the application's rich domain model, protecting the core logic from external influence.

## **Internal Logic Flow Diagram**

Code snippet

graph TD  
    subgraph External Systems  
        Exchange\[CTP/SOPT Exchange\]  
        NATS\[NATS Message Bus\]  
        ClickHouse\[ClickHouse DB\]  
    end

    subgraph "Market-Service Application"  
        subgraph "Infrastructure Layer"  
            GatewayAdapter\[Gateway Adapter\<br/\>(vnpy)\]  
            NatsPublisher\[NATS Publisher\]  
            ClickHouseRepo\[ClickHouse Repository\]  
        end

        subgraph "Cross-domain Layer"  
            ACL\[Anti-Corruption Layer\]  
        end

        subgraph "Application Layer"  
            UseCase\[Use Case Handler\<br/\>e.g., ProcessTick\]  
        end

        subgraph "Domain Layer"  
            Aggregate\[Domain Aggregate\<br/\>e.g., MarketDataStream\]  
        end  
    end

    Exchange \--\> GatewayAdapter  
    GatewayAdapter \-- Raw Data \--\> ACL  
    ACL \-- Domain Model \--\> UseCase  
    UseCase \-- Commands \--\> Aggregate  
    Aggregate \-- Domain Events \--\> UseCase  
    UseCase \-- Data to Persist \--\> ClickHouseRepo  
    UseCase \-- Events to Publish \--\> NatsPublisher  
    NatsPublisher \--\> NATS  
    ClickHouseRepo \--\> ClickHouse
