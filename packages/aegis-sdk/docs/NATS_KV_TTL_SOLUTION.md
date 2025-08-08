# NATS KV TTL Solution Documentation

## Problem
NATS KV store entries were not expiring automatically, causing stale services to remain in the registry indefinitely.

## Root Cause Analysis
1. **Per-message TTL (`allow_msg_ttl`) doesn't work reliably with KV stores** - While JetStream supports per-message TTL via the `Nats-TTL` header, this feature doesn't work consistently with the KV abstraction built on top of JetStream.

2. **KV is built on JetStream streams** - KV stores are actually JetStream streams with specific naming conventions (`KV_<bucket_name>`).

3. **Stream-level TTL (`max_age`) is the proper solution** - Instead of per-message TTL, configuring the stream with `max_age` provides reliable TTL for all entries.

## Solution Implementation

### 1. Helm Chart Configuration
Created a post-install job that creates the KV bucket with proper TTL:

```yaml
# helm/values-test.yaml
nats:
  kvStore:
    ttlSeconds: 30  # Configurable TTL in seconds
```

### 2. KV Bucket Creation with TTL
The post-install job creates the KV bucket using JetStream API directly:

```bash
# Create KV bucket with stream-level TTL (max_age)
cat <<EOF | nats req '$JS.API.STREAM.CREATE' -
{
  "name": "KV_service_registry",
  "subjects": ["$KV.service_registry.>"],
  "retention": "limits",
  "max_msgs_per_subject": 10,
  "max_bytes": -1,
  "max_age": 30000000000,  # 30 seconds in nanoseconds
  "max_msg_size": 1048576,
  "storage": "file",
  "allow_direct": true,
  "allow_rollup_hdrs": true,
  "deny_delete": false,
  "deny_purge": false,
  "discard": "old",
  "allow_msg_ttl": true,  # Also enable per-message TTL for future use
  "replicas": 1
}
EOF
```

Or using NATS CLI directly:
```bash
nats kv add service_registry --ttl 30s --replicas 1 --storage file
```

### 3. Key Configuration Parameters
- **max_age**: Stream-level TTL in nanoseconds (30s = 30000000000ns)
- **max_msgs_per_subject**: Limit per key (10 revisions)
- **discard**: "old" - Discard oldest messages when limits reached
- **allow_msg_ttl**: true - Enable per-message TTL for future compatibility

### 4. Testing and Verification
```bash
# Add test entry
nats kv put service_registry test-key "test value"

# Wait for TTL (30s)
sleep 35

# Verify entry is gone
nats kv get service_registry test-key  # Should return "key not found"
```

### 5. Integration with SDK
The SDK doesn't need to change - it continues to use the KV store normally. The TTL is handled at the stream level automatically.

```python
# SDK usage remains the same
await kv_store.put(key, value)  # No TTL options needed
# Entry will automatically expire after 30 seconds
```

## Important Notes

1. **TTL applies to ALL entries** - Stream-level TTL affects all entries in the bucket equally.

2. **TTL is set at bucket creation** - Cannot be changed without recreating the bucket.

3. **Existing entries without TTL** - Old entries created before TTL configuration will not expire. Need manual cleanup or bucket recreation.

4. **Per-message TTL still doesn't work** - Even with `allow_msg_ttl=true`, per-message TTL via headers doesn't work reliably with KV stores.

5. **Monitor-API cleanup still useful** - The periodic cleanup task in monitor-api serves as a backup for any edge cases.

## Deployment Process

1. **New Installation**:
   ```bash
   helm install aegis-trader ./helm -n aegis-trader -f ./helm/values-test.yaml
   ```

2. **Upgrade Existing**:
   ```bash
   # Will recreate KV bucket with TTL if max_age=0
   helm upgrade aegis-trader ./helm -n aegis-trader -f ./helm/values-test.yaml
   ```

3. **Manual Creation** (if needed):
   ```bash
   kubectl exec -it <nats-pod> -n aegis-trader -- nats kv add service_registry --ttl 30s
   ```

## Monitoring TTL

Check bucket configuration:
```bash
kubectl exec <nats-pod> -n aegis-trader -- nats kv info service_registry
```

Look for:
- `Maximum Age: 30.00s` - Confirms TTL is set
- `Per-Key TTL Supported: false` - Expected (KV doesn't support per-key TTL)

## Troubleshooting

1. **Entries not expiring**: Check if bucket has `max_age` set
2. **Old entries still present**: Recreate bucket or manually clean
3. **TTL too short/long**: Adjust `nats.kvStore.ttlSeconds` in values.yaml

## Future Improvements

1. Support per-key TTL when NATS implements it for KV stores
2. Dynamic TTL adjustment without bucket recreation
3. Separate TTL for different service types

## References
- [NATS JetStream Documentation](https://docs.nats.io/nats-concepts/jetstream)
- [NATS KV Store Documentation](https://docs.nats.io/nats-concepts/jetstream/key-value-store)
- [GitHub Issue #3653](https://github.com/nats-io/nats-server/issues/3653) - KV TTL issues
