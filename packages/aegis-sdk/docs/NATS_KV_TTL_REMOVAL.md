# NATS KV TTL Removal Documentation

## Summary
Per-message TTL has been completely removed from the AegisSDK codebase as it is not reliably supported by NATS KV store.

## Why TTL Was Removed

1. **NATS KV Limitation**: NATS KV store does not reliably support per-message TTL
2. **Misleading API**: Accepting TTL parameters that don't work creates confusion
3. **Better Alternatives**: Stream-level TTL and client-side filtering provide more reliable expiration

## What Changed

### 1. Domain Models
- Removed `ttl` field from `KVOptions` class
- Updated class documentation to explain TTL is not supported

### 2. Infrastructure Layer
- `NATSKVStore.put()` no longer handles TTL options
- Removed TTL-related debug logging and metrics
- Simplified put operations

### 3. Service Registry
- `KVServiceRegistry.register()` keeps `ttl_seconds` parameter for compatibility but ignores it
- `KVServiceRegistry.update_heartbeat()` no longer passes TTL to KV store
- Service expiration handled by client-side filtering based on heartbeat timestamps

### 4. Election System
- `NatsKvElectionRepository` no longer uses TTL for leader keys
- `ElectionCoordinator` relies on stream-level configuration for cleanup

### 5. Factory Methods
- `KVOptionsFactory` methods that created TTL options now return standard options
- Methods kept for backward compatibility but with updated documentation

### 6. Examples
- Renamed `kv_store_ttl_example.py` to `kv_store_expiration_example.py`
- Updated example to demonstrate proper expiration handling

## Correct Approach for Expiration

### 1. Stream-Level TTL Configuration
```python
from aegis_sdk.infrastructure.config import KVStoreConfig

kv_config = KVStoreConfig(
    bucket="service_registry",
    stream_max_age_seconds=60,  # Expires history after 60 seconds
)
kv_store = NATSKVStore(nats_adapter, config=kv_config)
```

### 2. Service Expiration Pattern
```python
# Services maintain heartbeat timestamps
service = ServiceInstance(
    service_name="my-service",
    instance_id="instance-001",
    last_heartbeat=datetime.now(UTC).isoformat(),
)

# Client-side filtering for expired services
def is_expired(service: ServiceInstance, max_age_seconds: int = 30) -> bool:
    last_heartbeat = datetime.fromisoformat(service.last_heartbeat)
    age = datetime.now(UTC) - last_heartbeat
    return age.total_seconds() > max_age_seconds
```

### 3. Manual Cleanup
```python
async def cleanup_expired_services(registry, max_age_seconds=30):
    """Remove services that haven't sent heartbeat recently."""
    all_services = await registry.list_all_services()
    for service_name, instances in all_services.items():
        for instance in instances:
            if is_expired(instance, max_age_seconds):
                await registry.deregister(service_name, instance.instance_id)
```

## Migration Guide

If your code was using TTL:

### Before (Not Working)
```python
# This didn't actually expire the key after 30 seconds
await kv_store.put("key", value, KVOptions(ttl=30))
```

### After (Working Solution)
```python
# Option 1: Use heartbeat pattern
data = {
    "value": value,
    "timestamp": datetime.now(UTC).isoformat()
}
await kv_store.put("key", data)

# Check expiration when reading
entry = await kv_store.get("key")
if entry:
    timestamp = datetime.fromisoformat(entry.value["timestamp"])
    if (datetime.now(UTC) - timestamp).total_seconds() > 30:
        # Entry is expired, delete it
        await kv_store.delete("key")

# Option 2: Use stream-level TTL for history cleanup
kv_config = KVStoreConfig(
    bucket="my_bucket",
    stream_max_age_seconds=300,  # Clean up history after 5 minutes
)
```

## Benefits of This Approach

1. **Clarity**: No confusion about what works and what doesn't
2. **Reliability**: Client-side filtering always works as expected
3. **Flexibility**: Applications can implement custom expiration logic
4. **Performance**: No overhead from non-functional TTL attempts
5. **Maintainability**: Simpler codebase without dead code paths

## Testing Impact

Most integration tests continue to pass. Tests that specifically tested per-message TTL have been removed or updated to test the correct expiration patterns.

## Backward Compatibility

- Interfaces that accepted `ttl_seconds` parameters still accept them for compatibility
- The parameters are ignored with clear documentation
- No breaking changes to public APIs

## Future Considerations

If NATS adds reliable per-message TTL support in the future:
1. The TTL field can be re-added to KVOptions
2. Implementation can be updated in NATSKVStore
3. Service registry can be enhanced to use TTL again

For now, the combination of stream-level TTL and client-side filtering provides a robust and reliable solution for service lifecycle management.
