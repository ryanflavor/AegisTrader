#!/usr/bin/env python3
"""
Interactive CLI Client - Test RPC calls interactively.

This example demonstrates:
- Interactive command-line interface for testing services
- Service discovery and selection
- Dynamic RPC method invocation
- Response formatting and error handling

Usage:
    python interactive_client.py

Then use commands like:
    > discover calculator
    > call calculator add {"a": 5, "b": 3}
    > call order-processor create_order {"customer_id": "C123", "total_amount": 99.99}
    > help
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from aegis_sdk.developer.bootstrap import quick_setup

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Keep quiet for interactive mode
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)


class InteractiveClient:
    """
    Interactive CLI client for testing SDK services.

    Provides a REPL interface for discovering services,
    making RPC calls, and exploring the system.
    """

    def __init__(self):
        self.client = None
        self.discovered_services = {}
        self.last_result = None
        self.history = []

    async def connect(self) -> None:
        """Connect to NATS and setup client."""
        print("🔌 Connecting to NATS cluster...")
        self.client = await quick_setup("interactive-client", as_client=True)
        print("✅ Connected successfully!")
        print()

    async def cmd_help(self, args: str) -> None:
        """Show help information."""
        print("\n📚 AVAILABLE COMMANDS:")
        print("-" * 50)
        print("  discover <service-type>")
        print("    Find all instances of a service type")
        print("    Example: discover calculator")
        print()
        print("  call <service-type> <method> <params>")
        print("    Call an RPC method on a service")
        print('    Example: call calculator add {"a": 5, "b": 3}')
        print()
        print("  list")
        print("    List all discovered services")
        print()
        print("  services")
        print("    Show all service types in the registry")
        print()
        print("  health <service-type>")
        print("    Check health of service instances")
        print()
        print("  watch <service-type>")
        print("    Watch for service changes (press Ctrl+C to stop)")
        print()
        print("  benchmark <service-type> <method> <params> <count>")
        print("    Benchmark RPC calls")
        print('    Example: benchmark calculator add {"a": 1, "b": 2} 100')
        print()
        print("  history")
        print("    Show command history")
        print()
        print("  clear")
        print("    Clear the screen")
        print()
        print("  help")
        print("    Show this help message")
        print()
        print("  exit / quit")
        print("    Exit the client")
        print("-" * 50)
        print()

    async def cmd_discover(self, args: str) -> None:
        """Discover service instances."""
        if not args:
            print("❌ Usage: discover <service-type>")
            return

        service_type = args.strip()
        print(f"🔍 Discovering {service_type} services...")

        try:
            instances = await self.client.discover_services(service_type)

            if not instances:
                print(f"  No instances of {service_type} found")
            else:
                self.discovered_services[service_type] = instances
                print(f"  Found {len(instances)} instance(s):")
                for inst in instances:
                    print(f"    • {inst.instance_id}")
                    print(f"      Status: {inst.health_status}")
                    print(f"      Last seen: {inst.last_heartbeat}")
                    if inst.metadata:
                        print(f"      Metadata: {json.dumps(inst.metadata, indent=8)[:200]}...")

        except Exception as e:
            print(f"❌ Error: {e}")

    async def cmd_call(self, args: str) -> None:
        """Make an RPC call to a service."""
        parts = args.split(maxsplit=2)
        if len(parts) < 3:
            print("❌ Usage: call <service-type> <method> <params>")
            print('  Example: call calculator add {"a": 5, "b": 3}')
            return

        service_type, method, params_str = parts

        try:
            # Parse parameters
            params = json.loads(params_str)

            print(f"📞 Calling {service_type}.{method}({params_str})")

            # Make the RPC call
            result = await self.client.call_rpc(
                service_type=service_type, method=method, params=params
            )

            self.last_result = result

            # Pretty print the result
            print("✅ Response:")
            print(json.dumps(result, indent=2, default=str))

        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON parameters: {e}")
        except Exception as e:
            print(f"❌ RPC Error: {e}")

    async def cmd_list(self, args: str) -> None:
        """List all discovered services."""
        if not self.discovered_services:
            print("📋 No services discovered yet. Use 'discover' command first.")
            return

        print("\n📋 DISCOVERED SERVICES:")
        print("-" * 50)
        for service_type, instances in self.discovered_services.items():
            print(f"  {service_type}:")
            for inst in instances:
                status_icon = "✅" if inst.health_status == "healthy" else "⚠️"
                print(f"    {status_icon} {inst.instance_id}")
        print("-" * 50)
        print()

    async def cmd_services(self, args: str) -> None:
        """Show all service types in the registry."""
        print("🔍 Fetching all service types...")

        # Discover common service types
        common_types = [
            "calculator",
            "order-processor",
            "event-publisher",
            "event-subscriber",
            "metrics-collector",
            "echo-service",
        ]

        found_types = []
        for service_type in common_types:
            instances = await self.client.discover_services(service_type)
            if instances:
                found_types.append((service_type, len(instances)))

        if not found_types:
            print("  No services found in registry")
        else:
            print("\n📊 SERVICE TYPES:")
            print("-" * 50)
            for service_type, count in found_types:
                print(f"  • {service_type} ({count} instance(s))")
            print("-" * 50)
            print()

    async def cmd_health(self, args: str) -> None:
        """Check health of service instances."""
        if not args:
            print("❌ Usage: health <service-type>")
            return

        service_type = args.strip()
        print(f"🏥 Checking health of {service_type} services...")

        try:
            instances = await self.client.discover_services(service_type)

            if not instances:
                print(f"  No instances of {service_type} found")
            else:
                print(f"\n  Health Status for {service_type}:")
                print("  " + "-" * 40)

                for inst in instances:
                    age = (datetime.utcnow() - inst.last_heartbeat).total_seconds()

                    if age < 5:
                        status = "✅ Healthy"
                        health_bar = "████████████████████"
                    elif age < 10:
                        status = "⚠️ Warning"
                        health_bar = "████████████--------"
                    else:
                        status = "❌ Unhealthy"
                        health_bar = "████----------------"

                    print(f"  {inst.instance_id}:")
                    print(f"    Status: {status}")
                    print(f"    Health: [{health_bar}]")
                    print(f"    Last heartbeat: {age:.1f}s ago")

                    # Show metrics if available
                    if inst.metadata and "metrics" in inst.metadata:
                        metrics = inst.metadata["metrics"]
                        print("    Metrics:")
                        if "requests_total" in metrics:
                            print(f"      Requests: {metrics['requests_total']}")
                        if "error_rate" in metrics:
                            print(f"      Error rate: {metrics['error_rate']:.1f}%")
                        if "average_latency_ms" in metrics:
                            print(f"      Avg latency: {metrics['average_latency_ms']:.1f}ms")

                print("  " + "-" * 40)
                print()

        except Exception as e:
            print(f"❌ Error: {e}")

    async def cmd_watch(self, args: str) -> None:
        """Watch for service changes."""
        if not args:
            print("❌ Usage: watch <service-type>")
            return

        service_type = args.strip()
        print(f"👁️ Watching {service_type} services (press Ctrl+C to stop)...")

        try:
            last_state = {}

            while True:
                instances = await self.client.discover_services(service_type)

                # Build current state
                current_state = {inst.instance_id: inst.health_status for inst in instances}

                # Check for changes
                if current_state != last_state:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Service changes detected:")

                    # New instances
                    for inst_id in current_state:
                        if inst_id not in last_state:
                            print(f"  🟢 NEW: {inst_id}")

                    # Removed instances
                    for inst_id in last_state:
                        if inst_id not in current_state:
                            print(f"  🔴 REMOVED: {inst_id}")

                    # Status changes
                    for inst_id in current_state:
                        if inst_id in last_state and current_state[inst_id] != last_state[inst_id]:
                            print(
                                f"  🟡 CHANGED: {inst_id} ({last_state[inst_id]} → {current_state[inst_id]})"
                            )

                    last_state = current_state

                await asyncio.sleep(2)

        except KeyboardInterrupt:
            print("\n⏹️ Stopped watching")

    async def cmd_benchmark(self, args: str) -> None:
        """Benchmark RPC calls."""
        parts = args.split(maxsplit=3)
        if len(parts) < 4:
            print("❌ Usage: benchmark <service-type> <method> <params> <count>")
            print('  Example: benchmark calculator add {"a": 1, "b": 2} 100')
            return

        service_type, method, params_str, count_str = parts

        try:
            params = json.loads(params_str)
            count = int(count_str)

            print(f"⚡ Benchmarking {count} calls to {service_type}.{method}")
            print("  Running...")

            # Warm up
            await self.client.call_rpc(service_type, method, params)

            # Benchmark
            import time

            latencies = []
            errors = 0

            start_time = time.time()

            for i in range(count):
                try:
                    call_start = time.time()
                    await self.client.call_rpc(service_type, method, params)
                    latency = (time.time() - call_start) * 1000
                    latencies.append(latency)

                    # Progress indicator
                    if (i + 1) % 10 == 0:
                        print(f"  Progress: {i + 1}/{count}", end="\r")

                except Exception:
                    errors += 1

            total_time = time.time() - start_time

            # Calculate statistics
            if latencies:
                latencies.sort()
                avg_latency = sum(latencies) / len(latencies)
                p50 = latencies[int(len(latencies) * 0.50)]
                p95 = latencies[int(len(latencies) * 0.95)]
                p99 = latencies[int(len(latencies) * 0.99)]
                min_latency = latencies[0]
                max_latency = latencies[-1]

                print("\n📊 BENCHMARK RESULTS:")
                print("-" * 50)
                print(f"  Total calls: {count}")
                print(f"  Successful: {len(latencies)}")
                print(f"  Errors: {errors}")
                print(f"  Total time: {total_time:.2f}s")
                print(f"  Throughput: {count / total_time:.1f} req/s")
                print()
                print("  Latency (ms):")
                print(f"    Min: {min_latency:.2f}")
                print(f"    Avg: {avg_latency:.2f}")
                print(f"    P50: {p50:.2f}")
                print(f"    P95: {p95:.2f}")
                print(f"    P99: {p99:.2f}")
                print(f"    Max: {max_latency:.2f}")
                print("-" * 50)
                print()
            else:
                print("❌ All calls failed")

        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON parameters: {e}")
        except ValueError as e:
            print(f"❌ Invalid count: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")

    async def cmd_history(self, args: str) -> None:
        """Show command history."""
        if not self.history:
            print("📜 No command history yet")
            return

        print("\n📜 COMMAND HISTORY:")
        print("-" * 50)
        for i, cmd in enumerate(self.history[-20:], 1):  # Last 20 commands
            print(f"  {i:2d}. {cmd}")
        print("-" * 50)
        print()

    async def cmd_clear(self, args: str) -> None:
        """Clear the screen."""
        import os

        os.system("clear" if os.name == "posix" else "cls")

    async def run_interactive(self) -> None:
        """Run the interactive REPL."""
        print("\n" + "=" * 60)
        print("🎮 AEGIS SDK INTERACTIVE CLIENT")
        print("=" * 60)
        print("\nType 'help' for available commands or 'exit' to quit\n")

        while True:
            try:
                # Get user input
                cmd_line = input("> ").strip()

                if not cmd_line:
                    continue

                # Add to history
                self.history.append(cmd_line)

                # Parse command
                parts = cmd_line.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                # Handle commands
                if command in ["exit", "quit"]:
                    print("👋 Goodbye!")
                    break
                elif command == "help":
                    await self.cmd_help(args)
                elif command == "discover":
                    await self.cmd_discover(args)
                elif command == "call":
                    await self.cmd_call(args)
                elif command == "list":
                    await self.cmd_list(args)
                elif command == "services":
                    await self.cmd_services(args)
                elif command == "health":
                    await self.cmd_health(args)
                elif command == "watch":
                    await self.cmd_watch(args)
                elif command == "benchmark":
                    await self.cmd_benchmark(args)
                elif command == "history":
                    await self.cmd_history(args)
                elif command == "clear":
                    await self.cmd_clear(args)
                else:
                    print(f"❌ Unknown command: {command}")
                    print("Type 'help' for available commands")

            except KeyboardInterrupt:
                print("\n💡 Use 'exit' or 'quit' to leave")
            except EOFError:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")


async def main():
    """Main entry point."""
    client = InteractiveClient()

    try:
        await client.connect()
        await client.run_interactive()
    finally:
        if client.client:
            await client.client.stop()


if __name__ == "__main__":
    asyncio.run(main())
