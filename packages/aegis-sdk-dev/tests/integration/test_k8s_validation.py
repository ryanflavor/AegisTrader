#!/usr/bin/env python
"""Comprehensive validation test for aegis-sdk-dev with K8s."""

import asyncio
import json
import sys
from datetime import datetime

# Test configuration
TESTS = {
    "1. CLI Validation": {
        "command": "aegis-validate",
        "args": [
            "--service-name",
            "test-service",
            "--nats-url",
            "nats://localhost:4222",
            "--environment",
            "auto",
            "--json",
        ],
    },
    "2. K8s Environment Detection": {"function": "test_k8s_detection"},
    "3. NATS Connection": {"function": "test_nats_connection"},
    "4. Service Registration": {"function": "test_service_registration"},
    "5. Load Balancing": {"function": "test_load_balancing"},
}


async def test_k8s_detection():
    """Test K8s environment detection."""
    from aegis_sdk_dev.infrastructure.environment_adapter import EnvironmentAdapter

    adapter = EnvironmentAdapter()
    environment = adapter.detect_environment()
    in_kubernetes = adapter.is_kubernetes_environment()
    has_port_forward = adapter._check_port_forward()

    print(f"  Environment: {environment}")
    print(f"  In K8s: {in_kubernetes}")
    print(f"  Has port-forward: {has_port_forward}")

    return environment in ["kubernetes", "local"] and (in_kubernetes or has_port_forward)


async def test_nats_connection():
    """Test NATS connectivity."""
    try:
        import nats

        nc = await nats.connect("nats://localhost:4222")
        print(f"  Connected to NATS: {nc.is_connected}")
        print(f"  Server ID: {nc.connected_server_id}")

        # Test JetStream
        js = nc.jetstream()
        info = await js.account_info()
        print("  JetStream enabled: True")
        print(f"  Memory: {info.memory}/{info.limits.max_memory if info.limits else 'unlimited'}")

        await nc.close()
        return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


async def test_service_registration():
    """Test service registration in KV store."""
    try:
        from aegis_sdk_dev.quickstart.bootstrap import (
            cleanup_service_context,
            create_service_context,
        )

        # Create service context
        context = await create_service_context(
            nats_url="nats://localhost:4222", service_name="test-validation-service"
        )

        print(f"  Service registered: {context.service_name}")
        print(f"  Instance ID: {context.instance_id}")

        # Check if service is in registry
        kv = context.nats_client.jetstream().key_value(bucket="service_registry")
        keys = await kv.keys()
        service_keys = [k for k in keys if "test-validation" in k]
        print(f"  Registry entries: {len(service_keys)}")

        # Cleanup
        await cleanup_service_context(context)
        print("  Cleanup successful")

        return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


async def test_load_balancing():
    """Test load balancing across multiple instances."""
    try:
        import nats

        nc = await nats.connect("nats://localhost:4222")

        # Send multiple echo requests
        responses = []
        instances = set()

        for i in range(10):
            try:
                msg = await nc.request(
                    "echo.service.echo", json.dumps({"message": f"Test {i}"}).encode(), timeout=2.0
                )
                response = json.loads(msg.data)
                responses.append(response)
                instances.add(response.get("instance_id", "unknown"))
            except asyncio.TimeoutError:
                print(f"  Request {i} timed out")

        print("  Requests sent: 10")
        print(f"  Responses received: {len(responses)}")
        print(f"  Unique instances: {len(instances)}")
        print(f"  Instance IDs: {', '.join(list(instances)[:3])}")

        await nc.close()

        # Success if we got responses from multiple instances
        return len(instances) > 1

    except Exception as e:
        print(f"  Error: {e}")
        return False


async def run_cli_test(test_name, config):
    """Run CLI command test."""
    import subprocess

    cmd = ["uv", "run", config["command"]] + config["args"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd="/home/ryan/workspace/github/AegisTrader/packages/aegis-sdk-dev",
        )

        if "--json" in config["args"]:
            output = json.loads(result.stdout)
            print(f"  Valid: {output.get('is_valid', False)}")
            print(f"  Environment: {output.get('environment', 'unknown')}")
            if output.get("issues"):
                print(f"  Issues: {len(output['issues'])}")
        else:
            print(result.stdout[:200])

        return result.returncode == 0

    except Exception as e:
        print(f"  Error: {e}")
        return False


async def main():
    """Run all validation tests."""
    print("=" * 60)
    print("AEGIS-SDK-DEV K8S VALIDATION TEST SUITE")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    results = {}

    for test_name, config in TESTS.items():
        print(f"\n{test_name}")
        print("-" * 40)

        try:
            if "command" in config:
                success = await run_cli_test(test_name, config)
            else:
                test_func = globals()[config["function"]]
                success = await test_func()

            results[test_name] = "✅ PASS" if success else "❌ FAIL"
            print(f"  Result: {results[test_name]}")

        except Exception as e:
            results[test_name] = f"❌ ERROR: {e}"
            print(f"  Result: {results[test_name]}")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, result in results.items():
        print(f"{test_name}: {result}")

    passed = sum(1 for r in results.values() if "✅" in r)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
