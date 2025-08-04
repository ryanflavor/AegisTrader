# Shared Contracts

This package contains shared technical contracts and constants used across all AegisTrader services.

**Important**: This package does NOT contain business domain models. Each service should define its own domain models within its own boundaries.

## What's Included

### Constants
- **ServiceNames**: Standard service names (order-service, pricing-service, etc.)
- **EventPatterns**: Event naming patterns following `events.{domain}.{action}` convention
- **KVBuckets**: Standard KV bucket names
- **RPCPatterns**: Common RPC method names
- **ServiceDefaults**: Default configuration values

### Message Contracts
- **BaseEventContract**: Standard event format for all events
- **RPCRequestContract**: Standard RPC request format
- **RPCResponseContract**: Standard RPC response format
- **ServiceHealthContract**: Standard health check response
- **ServiceMetricsContract**: Standard metrics response

## Usage

```python
from shared_contracts import ServiceNames, EventPatterns, BaseEventContract

# Use standard service names
service_name = ServiceNames.ORDER_SERVICE

# Use standard event patterns
await service.publish_event(
    EventPatterns.ORDER_CREATED,
    {
        "order_id": "ORD-001",
        "symbol": "AAPL",
        # ... other order data
    }
)

# Subscribe to events using patterns
@service.subscribe(EventPatterns.ORDER_EVENTS)
async def handle_order_events(event):
    # Handle all order-related events
    pass
```

## Design Principles

1. **Technical Contracts Only**: This package only defines technical message formats and constants, not business logic
2. **Standard Patterns**: All events follow the `events.{domain}.{action}` pattern
3. **Consistency**: Ensures all services use the same naming conventions
4. **Extensibility**: Services can extend these contracts with their own domain-specific fields
