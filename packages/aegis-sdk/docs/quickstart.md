# AegisSDK Quickstart Guide

Get up and running with AegisSDK in under 5 minutes! This guide will walk you through setting up your local Kubernetes environment and running your first services.

## Prerequisites

Before you begin, ensure you have:
- Python 3.11+ installed
- Docker Desktop with Kubernetes enabled (or minikube/kind)
- kubectl configured and connected to your cluster
- 5 minutes of your time!

## 1. Quick Setup (< 2 minutes)

### Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/your-org/aegis-trader.git
cd aegis-trader

# Install AegisSDK
cd packages/aegis-sdk
pip install -e .
```

### Step 2: Setup Kubernetes Environment

Run our automated setup script:

```bash
# Make script executable
chmod +x scripts/setup_k8s_dev.sh

# Run setup
./scripts/setup_k8s_dev.sh
```

This script will:
- ✅ Check kubectl connectivity
- ✅ Create aegis-trader namespace
- ✅ Verify NATS deployment
- ✅ Setup port-forwarding to NATS (localhost:4222)
- ✅ Create KV buckets for service registry

Expected output:
```
=====================================
AegisSDK K8s Development Setup
=====================================
✓ kubectl is available
✓ Connected to Kubernetes cluster
✓ Namespace aegis-trader exists
✓ NATS service found
✓ Port forwarding started (PID: 12345)
✓ NATS is reachable on localhost:4222
✓ KV bucket 'service_registry' exists

Environment Setup Complete!
```

## 2. Your First Service (< 1 minute)

### The Simplest Service

Create a file `hello_service.py`:

```python
from aegis_sdk.developer import quick_setup
import asyncio

async def main():
    # Zero-config setup - automatically discovers K8s NATS
    service = await quick_setup("hello-service")

    # Define an RPC handler
    @service.rpc("greet")
    async def greet(params):
        name = params.get("name", "World")
        return {"message": f"Hello, {name}!"}

    # Start the service
    print("Service running on NATS...")
    await service.start()

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python hello_service.py
```

Expected output:
```
[INFO] Auto-discovered NATS at: nats://localhost:4222
[INFO] Service 'hello-service' registered
Service running on NATS...
[INFO] Heartbeat started (interval: 5s)
```

### Test Your Service

In another terminal, create `test_client.py`:

```python
from aegis_sdk.developer import quick_setup
import asyncio

async def main():
    client = await quick_setup("test-client")

    # Call the service
    response = await client.call_rpc(
        "hello-service",
        "greet",
        {"name": "AegisSDK"}
    )
    print(f"Response: {response}")

    await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python test_client.py
```

Expected output:
```
Response: {'message': 'Hello, AegisSDK!'}
```

## 3. Understanding Service Patterns (< 2 minutes)

AegisSDK provides two fundamental patterns:

### Pattern 1: Load-Balanced Services

Multiple instances share the load automatically:

```bash
# Terminal 1
INSTANCE_ID=worker-1 python hello_service.py

# Terminal 2
INSTANCE_ID=worker-2 python hello_service.py

# Terminal 3 - Client sees automatic load balancing
python test_client.py  # Request goes to worker-1
python test_client.py  # Request goes to worker-2
```

### Pattern 2: Single-Active Services

Only one leader processes requests, with automatic failover:

```python
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.domain.value_objects import FailoverPolicy

service = SingleActiveService(
    name="critical-service",
    failover_policy=FailoverPolicy.aggressive()  # <2s failover
)
```

## 4. Run Interactive Examples

### Option A: Interactive Menu

```bash
./scripts/run_examples.sh
```

This presents a menu:
```
Select an example to run:

  Basic Services:
  1) Echo Service (Load-Balanced)
  2) Echo Single Service (Single-Active)
  3) Pattern Comparison Demo

  Advanced Services:
  4) Order Processing Service
  5) Event Publisher
  ...
```

### Option B: Direct Execution

```bash
# Run specific examples
python aegis_sdk/examples/quickstart/echo_service.py
python aegis_sdk/examples/quickstart/interactive_client.py
python aegis_sdk/examples/quickstart/service_explorer.py
```

## 5. Validate Your Setup

Run the configuration validator:

```bash
python aegis_sdk/developer/config_validator.py
```

Expected output:
```
============================================================
AegisSDK Configuration Validation Report
============================================================

Status: ✅ VALID
Environment: local-k8s

Diagnostics:
  ✓ k8s_available: True
  ✓ nats_connected: True

INFO (3):
  [K8S] Using kubectl context: docker-desktop
  [K8S] NATS service found on port 4222
  [K8S] Port-forwarding appears to be active
```

## Common Commands

### Service Management
```bash
# Start a service
python my_service.py

# Run with specific instance ID
INSTANCE_ID=instance-1 python my_service.py

# Run with debug logging
DEBUG=true python my_service.py
```

### Testing
```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=aegis_sdk

# Run integration tests
pytest tests/integration/ -v
```

### Kubernetes Operations
```bash
# Check NATS pods
kubectl get pods -n aegis-trader

# Watch services register/deregister
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- nats kv watch service_registry

# Check NATS streams
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- nats stream ls
```

## What's Next?

Now that you have a working setup:

1. **Explore Examples**: Check out `/examples/quickstart/` for more patterns
2. **Build Your Service**: Use `aegis-quickstart` CLI to scaffold a new project
3. **Test Failover**: Run `./scripts/test_failover.sh` to see HA in action
4. **Read Architecture**: Learn about DDD and hexagonal architecture in our docs
5. **Join Community**: Get help and share your experience

## Troubleshooting

### NATS Connection Refused
```bash
# Ensure port-forwarding is active
kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222
```

### Service Not Registering
```bash
# Check KV bucket exists
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- nats kv ls

# Create if missing
kubectl exec -it -n aegis-trader aegis-trader-nats-box -- nats kv add service_registry
```

### Import Errors
```bash
# Ensure SDK is installed
cd packages/aegis-sdk
pip install -e .
```

## Quick Reference

| Task | Command |
|------|---------|
| Setup environment | `./scripts/setup_k8s_dev.sh` |
| Run examples menu | `./scripts/run_examples.sh` |
| Test failover | `./scripts/test_failover.sh` |
| Validate config | `python aegis_sdk/developer/config_validator.py` |
| Create new project | `aegis-quickstart my-project` |
| Interactive client | `python examples/quickstart/interactive_client.py` |
| Service explorer | `python examples/quickstart/service_explorer.py` |

## Success Metrics

You'll know your setup is working when:
- ✅ Services register and appear in service discovery
- ✅ RPC calls complete successfully
- ✅ Multiple instances load-balance automatically
- ✅ Failover happens in under 2 seconds
- ✅ Events flow between publishers and subscribers

---

**Need Help?**
- Check [troubleshooting.md](troubleshooting.md) for common issues
- Review [examples.md](examples.md) for detailed walkthroughs
- See [architecture.md](../../../docs/architecture.md) for design details

**Time Elapsed:** If you followed this guide step-by-step, you should now have a working AegisSDK environment in under 5 minutes! 🎉
