"""
Publishing Context (通用子域)

This infrastructure context handles event publishing and distribution:
- NATS JetStream integration for event streaming
- Message publishing and fan-out
- Event sourcing and replay capabilities
- Guaranteed delivery mechanisms

Key Components:
- EventPublisher: Publishes domain events to NATS
- StreamManager: Manages JetStream streams and consumers
- MessageRouter: Routes messages to appropriate topics
- DeliveryGuarantee: Ensures message delivery semantics

Responsibilities:
- Publish market data events to NATS JetStream
- Manage event streams and consumer groups
- Provide replay and event sourcing capabilities
- Ensure delivery guarantees (at-least-once, exactly-once)
"""
