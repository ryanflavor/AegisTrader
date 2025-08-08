# AegisSDK Troubleshooting Guide

This comprehensive guide helps you diagnose and resolve common issues when working with AegisSDK.

## Quick Diagnostics

Run this command first to check your environment:

```bash
python packages/aegis-sdk/aegis_sdk/developer/config_validator.py
```

## Common Issues and Solutions

### 1. NATS Connection Issues

#### Problem: Connection Refused
```
Error: nats: error: nats: no servers available for connection
```

**Diagnosis:**
```bash
# Check if NATS is running
kubectl get pods -n aegis-trader | grep nats

# Check port forwarding
ps aux | grep "kubectl port-forward"

# Test connectivity
nc -zv localhost 4222
```

**Solutions:**

1. **Start port forwarding:**
```bash
kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222
```

2. **If NATS is not running:**
```bash
# Deploy NATS
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm install aegis-trader-nats nats/nats -n aegis-trader \
  --set jetstream.enabled=true \
  --set jetstream.fileStorage.size=1Gi
```

3. **If namespace doesn't exist:**
```bash
kubectl create namespace aegis-trader
```

---

#### Problem: Connection Timeout
```
Error: nats: timeout connecting to NATS at localhost:4222
```

**Diagnosis:**
```bash
# Check K8s context
kubectl config current-context

# Check service status
kubectl get svc -n aegis-trader
```

**Solutions:**

1. **Wrong K8s context:**
```bash
# List contexts
kubectl config get-contexts

# Switch to correct context
kubectl config use-context docker-desktop
```

2. **Firewall blocking:**
```bash
# Check firewall (Linux)
sudo ufw status

# Allow port if needed
sudo ufw allow 4222
```

---

### 2. Service Registration Issues

#### Problem: Service Not Appearing in Registry
```
Warning: Service registered but not visible in discovery
```

**Diagnosis:**
```bash
# Check KV bucket
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- nats kv ls

# Watch registry
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- nats kv watch service_registry
```

**Solutions:**

1. **Create KV bucket if missing:**
```bash
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- \
  nats kv add service_registry --ttl=30s --replicas=1
```

2. **Check JetStream is enabled:**
```bash
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- nats stream ls
```

3. **Verify service name format:**
```python
# Service names must be alphanumeric with hyphens
# Good: "order-service", "payment-processor"
# Bad: "order_service", "payment.processor"
```

---

#### Problem: Service Immediately Deregisters
```
Info: Service registered
Warning: Service deregistered after 5 seconds
```

**Diagnosis:**
```python
# Check heartbeat configuration
print(f"Heartbeat interval: {service.heartbeat_interval}")
print(f"TTL: {service.ttl}")
```

**Solutions:**

1. **Heartbeat not running:**
```python
# Ensure service.start() is called
await service.start()

# Keep service running
await asyncio.Event().wait()  # Don't exit immediately
```

2. **TTL too short:**
```python
# Increase TTL (default is 30s)
service = Service(
    name="my-service",
    heartbeat_interval=5,  # Send heartbeat every 5s
    ttl=30  # Service expires after 30s without heartbeat
)
```

---

### 3. RPC Call Issues

#### Problem: RPC Timeout
```
Error: RPC call timed out after 5 seconds
```

**Diagnosis:**
```python
# Check if service exists
from aegis_sdk.developer import quick_setup

client = await quick_setup("debug-client")
services = await client.discover("target-service")
print(f"Found {len(services)} instances")
```

**Solutions:**

1. **Service not running:**
```bash
# Start the service
python your_service.py
```

2. **Wrong service name:**
```python
# Verify exact service name
# Service registration:
service = Service(name="order-service")

# Client must use exact name:
await client.call_rpc("order-service", "method", {})  # Correct
await client.call_rpc("order_service", "method", {})  # Wrong
```

3. **Increase timeout:**
```python
response = await client.call_rpc(
    "slow-service",
    "heavy-operation",
    params={},
    timeout=30  # Increase from default 5s
)
```

---

#### Problem: NOT_ACTIVE Error
```
Error: Service returned NOT_ACTIVE - not the leader
```

**Diagnosis:**
```python
# This is expected for SingleActiveService when calling standby
# Client should retry to find leader
```

**Solutions:**

1. **Implement retry logic:**
```python
async def call_with_retry(client, service, method, params, max_retries=3):
    for i in range(max_retries):
        try:
            return await client.call_rpc(service, method, params)
        except Exception as e:
            if "NOT_ACTIVE" in str(e) and i < max_retries - 1:
                await asyncio.sleep(0.5)  # Brief delay before retry
                continue
            raise
```

2. **Use provided retry helper:**
```python
from aegis_sdk.domain.value_objects import RetryPolicy

response = await client.call_rpc_with_retry(
    "single-active-service",
    "method",
    params={},
    retry_policy=RetryPolicy(max_attempts=3, initial_delay=0.5)
)
```

---

### 4. Failover Issues

#### Problem: Slow Failover
```
Warning: Failover took 8 seconds (expected <2s)
```

**Diagnosis:**
```bash
# Check leader election logs
kubectl logs -n aegis-trader <your-pod> | grep -i election

# Monitor KV store
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- \
  nats kv get service_registry elections.<service-name>
```

**Solutions:**

1. **Use aggressive failover policy:**
```python
from aegis_sdk.domain.value_objects import FailoverPolicy

service = SingleActiveService(
    name="critical-service",
    failover_policy=FailoverPolicy.aggressive()  # <2s failover
)
```

2. **Reduce heartbeat interval:**
```python
service = SingleActiveService(
    name="critical-service",
    heartbeat_interval=1,  # 1 second heartbeats
    election_timeout=2     # 2 second timeout
)
```

---

#### Problem: Split Brain (Multiple Leaders)
```
Error: Multiple instances claiming leadership
```

**Diagnosis:**
```bash
# Check election state
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- \
  nats kv get service_registry elections.<service-name>
```

**Solutions:**

1. **Reset election state:**
```bash
# Delete election key to force re-election
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- \
  nats kv del service_registry elections.<service-name>
```

2. **Ensure unique instance IDs:**
```python
import uuid
service = SingleActiveService(
    name="service",
    instance_id=f"instance-{uuid.uuid4().hex[:8]}"  # Unique ID
)
```

---

### 5. Event Issues

#### Problem: Events Not Received
```
Warning: Subscriber not receiving events
```

**Diagnosis:**
```bash
# Check subject matching
# Publisher: "orders.created"
# Subscriber: "orders.*" or "orders.created"
```

**Solutions:**

1. **Fix subject pattern:**
```python
# Publisher
await service.publish("orders.created", order_data)

# Subscriber - these will work:
await service.subscribe("orders.created", handler)  # Exact
await service.subscribe("orders.*", handler)       # Wildcard
await service.subscribe("orders.>", handler)       # Multi-level

# This won't work:
await service.subscribe("order.created", handler)   # Wrong subject
```

2. **Check subscription mode:**
```python
from aegis_sdk.domain.enums import SubscriptionMode

# For load balancing across instances
await service.subscribe(
    "events.*",
    handler,
    mode=SubscriptionMode.COMPETE  # Default
)

# For all instances to receive
await service.subscribe(
    "events.*",
    handler,
    mode=SubscriptionMode.BROADCAST
)
```

---

### 6. Performance Issues

#### Problem: High Latency
```
Warning: RPC latency >100ms
```

**Diagnosis:**
```python
# Measure latency
import time
start = time.time()
response = await client.call_rpc("service", "method", {})
latency = (time.time() - start) * 1000
print(f"Latency: {latency:.2f}ms")
```

**Solutions:**

1. **Check network:**
```bash
# Ping NATS
ping localhost

# Check K8s network
kubectl exec -it -n aegis-trader <pod> -- ping <other-pod>
```

2. **Profile code:**
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
await service.handle_request()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

3. **Scale horizontally:**
```bash
# Add more instances for load-balanced services
for i in {1..5}; do
    INSTANCE_ID="worker-$i" python service.py &
done
```

---

### 7. Memory Issues

#### Problem: Memory Leak
```
Warning: Memory usage growing continuously
```

**Diagnosis:**
```python
import tracemalloc
import gc

# Start tracing
tracemalloc.start()

# ... run your service ...

# Check memory
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
```

**Solutions:**

1. **Clean up handlers:**
```python
# Remove unused handlers
service.remove_handler("old-method")

# Clear event subscriptions
await service.unsubscribe("unused.events")
```

2. **Limit cache size:**
```python
from functools import lru_cache

@lru_cache(maxsize=128)  # Limit cache size
def expensive_operation(param):
    return compute_result(param)
```

---

### 8. Development Environment Issues

#### Problem: Import Errors
```
Error: ModuleNotFoundError: No module named 'aegis_sdk'
```

**Solutions:**

1. **Install SDK in development mode:**
```bash
cd packages/aegis-sdk
pip install -e .
```

2. **Check Python path:**
```python
import sys
print(sys.path)

# Add if needed
sys.path.append('/path/to/aegis-trader/packages/aegis-sdk')
```

---

#### Problem: Wrong Python Version
```
Error: Python 3.11+ required
```

**Solutions:**

1. **Check version:**
```bash
python --version
```

2. **Use pyenv or conda:**
```bash
# pyenv
pyenv install 3.11.0
pyenv local 3.11.0

# conda
conda create -n aegis python=3.11
conda activate aegis
```

---

## Debugging Techniques

### 1. Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or via environment
# DEBUG=true python your_service.py
```

### 2. Use NATS CLI Tools

```bash
# Monitor all NATS traffic
nats sub ">"

# Watch specific subjects
nats sub "services.>"

# Check stream state
nats stream info

# View KV store
nats kv get service_registry <key>
```

### 3. Kubernetes Debugging

```bash
# View pod logs
kubectl logs -n aegis-trader <pod-name> -f

# Describe pod for events
kubectl describe pod -n aegis-trader <pod-name>

# Shell into pod
kubectl exec -it -n aegis-trader <pod-name> -- /bin/sh

# Port forward for debugging
kubectl port-forward -n aegis-trader <pod-name> 5678:5678
```

### 4. Python Debugger

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use debugpy for remote debugging
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
```

---

## Health Checks

### Quick Health Check Script

```python
# health_check.py
import asyncio
from aegis_sdk.developer import quick_setup

async def check_health():
    client = await quick_setup("health-checker")

    print("AegisSDK Health Check")
    print("=" * 40)

    # Check NATS
    try:
        await client.nats.publish("health.ping", b"test")
        print("✓ NATS: Connected")
    except:
        print("✗ NATS: Failed")

    # Check KV Store
    try:
        await client.kv_store.get("test")
        print("✓ KV Store: Accessible")
    except:
        print("✓ KV Store: Accessible (key not found is OK)")

    # Check Service Registry
    services = await client.discover_all()
    print(f"✓ Registry: {len(services)} services registered")

    await client.stop()

asyncio.run(check_health())
```

---

## Getting Help

### 1. Check Logs

Always check logs first:
```bash
# Application logs
tail -f application.log

# NATS server logs
kubectl logs -n aegis-trader aegis-trader-nats-0

# System logs
journalctl -xeu kubelet
```

### 2. Run Diagnostics

```bash
# Run configuration validator
python aegis_sdk/developer/config_validator.py

# Run health check
python health_check.py

# Test with examples
python examples/quickstart/echo_service.py
```

### 3. Community Resources

- GitHub Issues: Report bugs or request features
- Documentation: Check `/docs` folder
- Examples: Review `/examples` folder
- Tests: Look at test cases for usage patterns

---

## Prevention Checklist

Avoid issues by following these practices:

- [ ] Always run `setup_k8s_dev.sh` before development
- [ ] Use `quick_setup()` for automatic configuration
- [ ] Keep heartbeat interval < TTL/3
- [ ] Implement retry logic for single-active services
- [ ] Use unique instance IDs
- [ ] Handle graceful shutdown with try/finally
- [ ] Test failover scenarios regularly
- [ ] Monitor memory usage in long-running services
- [ ] Use structured logging for debugging
- [ ] Keep services stateless when possible

---

## Emergency Recovery

If everything is broken:

```bash
# 1. Reset NATS
kubectl delete pod -n aegis-trader aegis-trader-nats-0
kubectl wait --for=condition=ready pod -n aegis-trader aegis-trader-nats-0

# 2. Clear KV store
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- \
  nats kv purge service_registry --force

# 3. Restart port forwarding
pkill -f "kubectl port-forward"
kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222 &

# 4. Verify connectivity
nc -zv localhost 4222

# 5. Run validation
python aegis_sdk/developer/config_validator.py
```

---

Remember: Most issues are related to connectivity or configuration. Start with the validator and work through the diagnostics systematically.
