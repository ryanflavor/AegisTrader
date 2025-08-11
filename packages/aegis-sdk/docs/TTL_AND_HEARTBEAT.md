# TTL and Heartbeat Documentation for AegisSDK

## Overview

This document explains how TTL (Time-To-Live) and heartbeat mechanisms work in AegisSDK, particularly for service registration and discovery.

## Key Concepts

### NATS KV TTL Limitations

NATS KV store has specific limitations regarding TTL:

1. **No Reliable Per-Key TTL**: NATS KV does not support per-message/per-key TTL reliably when using the KV abstraction
2. **Stream-Level TTL**: Stream `max_age` affects the entire stream's message retention but does NOT automatically expire individual KV entries
3. **Latest Value Persistence**: KV stores always keep the latest value for each key, regardless of stream TTL settings

### Solution: Heartbeat-Based Lifecycle

Due to NATS KV limitations, AegisSDK uses a heartbeat-based approach:

1. **Service Registration**: Services register with a timestamp
2. **Periodic Heartbeat**: Services must send heartbeats to update their timestamp
3. **Stale Detection**: Consumers filter out entries based on heartbeat age
4. **Manual Cleanup**: Stale entries are periodically cleaned up by maintenance tasks

## Implementation Details

### Service Side (Publishers)

Services MUST implement a heartbeat loop to maintain their registration:

```python
# Example from echo service
async def _heartbeat_loop(self) -> None:
    """Periodic heartbeat update loop."""
    while True:
        try:
            await asyncio.sleep(15)  # Update every 15 seconds (half of TTL)
            await self.update_heartbeat()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Error in heartbeat loop: {e}")
            await asyncio.sleep(5)  # Brief delay on error
```

**Best Practices:**
- Heartbeat interval should be less than half of the expected TTL
- Default: 15-second heartbeat with 30-second TTL threshold
- Handle failures gracefully with retry logic

### Consumer Side (Monitor/Discovery)

Consumers MUST filter stale entries based on heartbeat age:

```python
def _is_stale(self, instance: ServiceInstance) -> bool:
    """Check if instance is stale based on heartbeat."""
    if not instance.last_heartbeat:
        return True

    age = (datetime.now(UTC) - instance.last_heartbeat).total_seconds()
    threshold = 35  # TTL (30s) + buffer (5s)
    return age > threshold
```

**Filtering Strategy:**
- Calculate age from last heartbeat timestamp
- Apply threshold (typically TTL + small buffer)
- Filter out stale entries before returning to clients

### Stream-Level Configuration

While stream-level TTL doesn't expire KV entries, it can be used for:
- Limiting historical data retention
- Reducing storage for old revisions
- Compliance with data retention policies

```python
config = KVStoreConfig(
    bucket="service_registry",
    stream_max_age_seconds=86400,  # Keep history for 24 hours
)
```

## Service Patterns

### Using SDK's Service Class

The SDK's `Service` class includes automatic heartbeat:

```python
from aegis_sdk.application.service import Service

service = Service(
    service_name="my-service",
    heartbeat_interval=10,  # Heartbeat every 10 seconds
    registry_ttl=30,        # 30-second TTL
)
await service.start()  # Heartbeat starts automatically
```

### Custom Implementation

If not using the SDK's Service class, implement heartbeat manually:

```python
class MyService:
    async def start(self):
        # Register service
        await self.registry.register(self.instance, ttl_seconds=30)

        # Start heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        # Deregister
        await self.registry.deregister(self.instance)
```

## Testing Considerations

### What NOT to Test
- Per-key TTL expiration (not supported by NATS KV)
- Automatic entry expiration based on stream TTL
- KV entry deletion after TTL timeout

### What TO Test
- Heartbeat update functionality
- Stale entry filtering logic
- Service registration/deregistration flow
- Heartbeat failure recovery

## Migration Guide

If migrating from systems with true TTL support:

1. **Add Heartbeat Logic**: Ensure all services implement heartbeat loops
2. **Update Consumers**: Add stale filtering to all service discovery consumers
3. **Monitor Heartbeats**: Add monitoring for heartbeat failures
4. **Cleanup Tasks**: Implement periodic cleanup for orphaned entries

## Troubleshooting

### Common Issues

1. **Services Not Appearing**: Check if heartbeat is running
2. **Services Not Disappearing**: Verify stale filtering is implemented
3. **Intermittent Visibility**: Check heartbeat interval vs TTL threshold
4. **Memory Growth**: Implement cleanup tasks for old entries

### Debug Checklist

- [ ] Is the service sending heartbeats?
- [ ] Is the heartbeat interval appropriate?
- [ ] Is the consumer filtering stale entries?
- [ ] Is the TTL threshold configured correctly?
- [ ] Are cleanup tasks running?

## Summary

- NATS KV does not support automatic per-key TTL expiration
- Services must implement heartbeat loops to maintain registration
- Consumers must filter stale entries based on heartbeat age
- Stream-level TTL only affects historical data retention
- The combination of heartbeats + filtering provides TTL-like behavior
