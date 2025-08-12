# Service Patterns in AegisSDK

## Executive Summary

AegisSDK provides **two fundamental service patterns**, not three separate service types. Understanding this distinction is crucial for proper architecture design.

## The Two Core Patterns

### 1. Load-Balanced Service Pattern
- **Implementation:** `Service` class
- **Behavior:** All instances can process requests
- **Load Distribution:** Natural load balancing via NATS
- **Use Cases:** Stateless services, REST APIs, query services

### 2. Sticky Single-Active Pattern
- **Implementation:** `SingleActiveService` class + client-side retry
- **Server Behavior:** Only leader processes exclusive requests
- **Client Behavior:** Automatic retry on NOT_ACTIVE errors
- **Use Cases:** Order processing, database migrations, singleton operations

## Common Misconception

❌ **Incorrect:** "There are three service types: Service, SingleActiveService, and StickyActiveService"

✅ **Correct:** "There are two service patterns: Load-Balanced and Sticky Single-Active"

## Why No Separate StickyActiveService Class?

The design follows the principle of **"mechanism vs policy separation"**:

1. **Server provides mechanism:** SingleActiveService determines who is the leader
2. **Client decides policy:** Whether to retry (sticky) or give up

This separation provides flexibility:
- Same service can be used with different retry policies
- No coupling between server implementation and client behavior
- Simpler codebase with fewer service types

## Implementation Guide

### Server Side (SingleActiveService)

```python
from aegis_sdk.application.single_active_service import SingleActiveService

class OrderProcessor(SingleActiveService):
    async def on_start(self):
        @self.exclusive_rpc("process_order")
        async def process_order(params):
            # Only leader executes this
            return {"status": "processed"}
```

### Client Side (Sticky Behavior)

```python
from aegis_sdk.domain.value_objects import RetryPolicy

# Configure retry for sticky behavior
retry_policy = RetryPolicy(
    max_retries=5,
    retryable_errors=["NOT_ACTIVE"],  # Key: retry on NOT_ACTIVE
    initial_delay=Duration(seconds=0.1),
    backoff_multiplier=2.0
)

# Client automatically retries until finding the leader
response = await rpc_call(
    service="order-processor",
    method="process_order",
    retry_policy=retry_policy
)
```

## Decision Tree

```
Need exclusive processing?
├── NO → Use Service (load-balanced)
└── YES → Use SingleActiveService
          └── Always configure client retry (sticky behavior)
```

## Key Takeaways

1. **Two patterns, not three:** Load-Balanced and Sticky Single-Active
2. **Sticky is client behavior:** Achieved through retry configuration
3. **SingleActiveService needs retry:** Without client retry, it's practically useless
4. **Flexibility by design:** Clients choose their reliability requirements

## Migration Notes

If your code references `StickyActiveService`:
1. Replace with `SingleActiveService` on the server
2. Add `RetryPolicy` or `StickyActiveConfig` on the client
3. The combination achieves the same "sticky" behavior
