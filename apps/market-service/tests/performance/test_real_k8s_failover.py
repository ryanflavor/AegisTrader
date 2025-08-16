#!/usr/bin/env python3
"""
REAL K8s failover test - measures actual pod deletion and recovery time
"""

import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_market_service_pods():
    """Get list of market-service pods"""
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", "aegis-trader", "-o", "name"],
        capture_output=True,
        text=True,
    )
    pods = []
    for line in result.stdout.strip().split("\n"):
        if "market-service" in line:
            pod_name = line.replace("pod/", "")
            pods.append(pod_name)
    return pods


def get_leader_pod():
    """Find which pod is the current leader by checking logs"""
    pods = get_market_service_pods()

    for pod in pods:
        result = subprocess.run(
            ["kubectl", "logs", pod, "-n", "aegis-trader", "--tail=100"],
            capture_output=True,
            text=True,
        )
        if "Leadership acquired" in result.stdout or "I am the leader" in result.stdout:
            return pod

    # If no explicit leader found, assume first pod
    return pods[0] if pods else None


def delete_pod(pod_name):
    """Force delete a pod"""
    print(f"Deleting pod {pod_name}...")
    subprocess.run(
        ["kubectl", "delete", "pod", pod_name, "-n", "aegis-trader", "--force", "--grace-period=0"],
        capture_output=True,
    )


def wait_for_new_leader(old_leader, timeout=30):
    """Wait for a new leader to be elected"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        pods = get_market_service_pods()

        # Check if we have healthy pods (excluding old leader)
        active_pods = [p for p in pods if p != old_leader]

        if active_pods:
            # Check if any pod has taken leadership
            for pod in active_pods:
                result = subprocess.run(
                    ["kubectl", "logs", pod, "-n", "aegis-trader", "--tail=20"],
                    capture_output=True,
                    text=True,
                )
                if "Leadership acquired" in result.stdout or "leader" in result.stdout.lower():
                    return pod, time.time() - start_time

        time.sleep(1)

    return None, time.time() - start_time


def main():
    print("\n" + "=" * 60)
    print("  REAL K8s Failover Test")
    print("=" * 60 + "\n")

    # Step 1: Check current state
    print("Step 1: Checking current deployment...")
    pods = get_market_service_pods()

    if not pods:
        print("❌ No market-service pods found!")
        print("   Deploy with: make deploy-to-kind-fast")
        return 1

    print(f"✓ Found {len(pods)} market-service pods:")
    for pod in pods:
        print(f"  - {pod}")

    if len(pods) < 2:
        print("\n⚠ Need at least 2 replicas for failover test")
        print("  Scaling to 3 replicas...")
        subprocess.run(
            [
                "kubectl",
                "scale",
                "deployment",
                "market-service",
                "-n",
                "aegis-trader",
                "--replicas=3",
            ],
            capture_output=True,
        )
        time.sleep(10)
        pods = get_market_service_pods()
        print(f"✓ Scaled to {len(pods)} replicas")

    # Step 2: Identify leader
    print("\nStep 2: Identifying current leader...")
    leader = get_leader_pod()

    if not leader:
        print("⚠ Could not identify leader, using first pod")
        leader = pods[0]

    print(f"✓ Current leader: {leader}")

    # Step 3: Delete leader and measure failover
    print("\nStep 3: Testing failover...")
    print(f"Deleting leader pod: {leader}")

    start_time = time.time()
    delete_pod(leader)

    print("Waiting for new leader election...")
    new_leader, failover_time = wait_for_new_leader(leader)

    # Step 4: Report results
    print("\n" + "=" * 60)
    print("  Test Results")
    print("=" * 60)

    if new_leader:
        print("✓ FAILOVER SUCCESSFUL")
        print(f"  Old leader: {leader}")
        print(f"  New leader: {new_leader}")
        print(f"  Failover time: {failover_time:.2f} seconds")

        if failover_time < 2:
            print("  ✓ Met target: < 2 seconds")
        elif failover_time < 10:
            print("  ⚠ Acceptable: < 10 seconds (K8s overhead)")
        else:
            print("  ❌ Too slow: > 10 seconds")
    else:
        print("❌ FAILOVER FAILED")
        print(f"  No new leader elected after {failover_time:.2f} seconds")

    # Step 5: Check final state
    print("\nFinal state:")
    final_pods = get_market_service_pods()
    print(f"  Active pods: {len(final_pods)}")
    for pod in final_pods:
        print(f"    - {pod}")

    return 0 if new_leader else 1


if __name__ == "__main__":
    sys.exit(main())
