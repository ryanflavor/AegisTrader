#!/usr/bin/env python3
"""
Service Discovery Explorer

Interactive tool for exploring registered services, their instances,
capabilities, health status, and metadata in real-time.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from aegis_sdk.domain.enums import ServiceStatus
from aegis_sdk.domain.models import ServiceInstance
from aegis_sdk.infrastructure.basic_service_discovery import BasicServiceDiscovery
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore


class ExplorerMode(str, Enum):
    """Explorer display modes."""

    LIST = "list"
    TREE = "tree"
    DETAILED = "detailed"
    WATCH = "watch"


class ServiceFilter(BaseModel):
    """Filters for service exploration."""

    name_pattern: str | None = Field(default=None)
    status_filter: ServiceStatus | None = Field(default=None)
    include_metadata: bool = Field(default=True)
    include_inactive: bool = Field(default=False)


class ServiceExplorer:
    """
    Service discovery explorer following DDD principles.

    This is an EXTERNAL CLIENT pattern - exploring services
    without being a service itself (like monitor-api).
    """

    def __init__(self, filter_config: ServiceFilter | None = None):
        """Initialize the service explorer."""
        self.filter = filter_config or ServiceFilter()
        self.console = Console()
        self.nats_adapter: NATSAdapter | None = None
        self.registry: KVServiceRegistry | None = None
        self.discovery: BasicServiceDiscovery | None = None
        self.services_cache: dict[str, list[ServiceInstance]] = {}

    async def connect(self) -> None:
        """Connect to NATS and set up service discovery."""
        # Direct infrastructure setup (external client pattern)
        self.nats_adapter = NATSAdapter()
        await self.nats_adapter.connect("nats://localhost:4222")

        # Set up KV store and registry
        kv_store = NATSKVStore(self.nats_adapter)
        await kv_store.connect("service_registry")

        self.registry = KVServiceRegistry(kv_store)
        self.discovery = BasicServiceDiscovery(self.registry)

        self.console.print("[green]✓ Connected to service registry[/green]")

    async def discover_all_services(self) -> dict[str, list[ServiceInstance]]:
        """Discover all registered services."""
        services: dict[str, list[ServiceInstance]] = {}

        # Get all service names from registry
        all_instances = await self.registry.list_services()

        # Group instances by service name
        for instance in all_instances:
            service_name = instance.service_name
            if service_name not in services:
                services[service_name] = []
            services[service_name].append(instance)

        # Apply filters
        if self.filter.name_pattern:
            services = {
                name: instances
                for name, instances in services.items()
                if self.filter.name_pattern in name
            }

        if self.filter.status_filter:
            for name in list(services.keys()):
                services[name] = [
                    inst for inst in services[name] if inst.status == self.filter.status_filter
                ]
                if not services[name]:
                    del services[name]

        if not self.filter.include_inactive:
            for name in list(services.keys()):
                services[name] = [
                    inst for inst in services[name] if inst.status != ServiceStatus.SHUTDOWN
                ]
                if not services[name]:
                    del services[name]

        self.services_cache = services
        return services

    def render_service_list(self, services: dict[str, list[ServiceInstance]]) -> None:
        """Render services as a simple list."""
        table = Table(title="Registered Services", show_header=True, header_style="bold magenta")

        table.add_column("Service Name", style="cyan")
        table.add_column("Instances", justify="right", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Capabilities", style="blue")

        for service_name, instances in sorted(services.items()):
            # Count active instances
            active_count = sum(1 for inst in instances if inst.status == ServiceStatus.ACTIVE)

            # Get unique capabilities
            capabilities = set()
            for inst in instances:
                capabilities.update(inst.capabilities)

            # Determine overall status
            if active_count == len(instances):
                status = "[green]● All Active[/green]"
            elif active_count > 0:
                status = f"[yellow]● {active_count}/{len(instances)} Active[/yellow]"
            else:
                status = "[red]● No Active[/red]"

            table.add_row(
                service_name, str(len(instances)), status, ", ".join(sorted(capabilities)) or "None"
            )

        self.console.print(table)

    def render_service_tree(self, services: dict[str, list[ServiceInstance]]) -> None:
        """Render services as a tree structure."""
        tree = Tree("Service Registry")

        for service_name, instances in sorted(services.items()):
            # Add service node
            service_branch = tree.add(f"[bold cyan]{service_name}[/bold cyan]")

            for instance in instances:
                # Status icon
                status_icon = {
                    ServiceStatus.ACTIVE: "[green]●[/green]",
                    ServiceStatus.STANDBY: "[yellow]●[/yellow]",
                    ServiceStatus.UNHEALTHY: "[red]●[/red]",
                    ServiceStatus.SHUTDOWN: "[dim]●[/dim]",
                }.get(instance.status, "○")

                # Instance info
                instance_text = f"{status_icon} {instance.instance_id}"

                # Add leader indicator if applicable
                if hasattr(instance, "metadata") and instance.metadata.get("is_leader"):
                    instance_text += " [bold green]👑 LEADER[/bold green]"

                instance_branch = service_branch.add(instance_text)

                # Add instance details
                if self.filter.include_metadata:
                    # Endpoint
                    instance_branch.add(f"Endpoint: {instance.endpoint}")

                    # Capabilities
                    if instance.capabilities:
                        cap_branch = instance_branch.add("Capabilities")
                        for cap in instance.capabilities:
                            cap_branch.add(f"[blue]{cap}[/blue]")

                    # Metadata
                    if instance.metadata:
                        meta_branch = instance_branch.add("Metadata")
                        for key, value in instance.metadata.items():
                            if key != "is_leader":  # Already shown
                                meta_branch.add(f"{key}: {value}")

                    # Health
                    if instance.health:
                        health_text = f"Health: {instance.health.score}%"
                        if instance.health.last_check:
                            last_check = datetime.fromisoformat(instance.health.last_check)
                            ago = (datetime.now() - last_check).total_seconds()
                            health_text += f" (checked {ago:.1f}s ago)"
                        instance_branch.add(health_text)

        self.console.print(tree)

    def render_detailed_view(self, services: dict[str, list[ServiceInstance]]) -> None:
        """Render detailed view of all services."""
        for service_name, instances in sorted(services.items()):
            # Service header
            panel = Panel(
                f"[bold]{service_name}[/bold]\n"
                f"Instances: {len(instances)} | "
                f"Active: {sum(1 for i in instances if i.status == ServiceStatus.ACTIVE)}",
                title=f"Service: {service_name}",
                border_style="cyan",
            )
            self.console.print(panel)

            # Instance details table
            table = Table(show_header=True, header_style="bold")

            table.add_column("Instance ID", style="dim")
            table.add_column("Status", style="yellow")
            table.add_column("Endpoint")
            table.add_column("Health")
            table.add_column("Metadata")

            for instance in instances:
                # Status with icon
                status_display = {
                    ServiceStatus.ACTIVE: "[green]● ACTIVE[/green]",
                    ServiceStatus.STANDBY: "[yellow]● STANDBY[/yellow]",
                    ServiceStatus.UNHEALTHY: "[red]● UNHEALTHY[/red]",
                    ServiceStatus.SHUTDOWN: "[dim]● SHUTDOWN[/dim]",
                }.get(instance.status, str(instance.status))

                # Health display
                health_display = "N/A"
                if instance.health:
                    health_display = f"{instance.health.score}%"
                    if instance.health.message:
                        health_display += f"\n{instance.health.message}"

                # Metadata display
                meta_display = ""
                if instance.metadata:
                    # Show important metadata fields
                    important_fields = ["is_leader", "election_status", "metrics", "version"]
                    for field in important_fields:
                        if field in instance.metadata:
                            value = instance.metadata[field]
                            if isinstance(value, dict):
                                value = json.dumps(value, indent=None)
                            meta_display += f"{field}: {value}\n"

                table.add_row(
                    instance.instance_id[:12] + "...",
                    status_display,
                    instance.endpoint,
                    health_display,
                    meta_display.strip(),
                )

            self.console.print(table)
            self.console.print()  # Spacing between services

    async def watch_services(self, interval: float = 2.0) -> None:
        """Watch services for changes in real-time."""
        self.console.print("[yellow]Watching services (Ctrl+C to stop)...[/yellow]\n")

        previous_state = {}

        try:
            while True:
                # Get current services
                current_services = await self.discover_all_services()

                # Detect changes
                changes = []

                # Check for new services
                for service_name in current_services:
                    if service_name not in previous_state:
                        changes.append(f"[green]+ New service: {service_name}[/green]")

                # Check for removed services
                for service_name in previous_state:
                    if service_name not in current_services:
                        changes.append(f"[red]- Removed service: {service_name}[/red]")

                # Check for instance changes
                for service_name in current_services:
                    if service_name in previous_state:
                        prev_instances = {inst.instance_id for inst in previous_state[service_name]}
                        curr_instances = {
                            inst.instance_id for inst in current_services[service_name]
                        }

                        # New instances
                        for inst_id in curr_instances - prev_instances:
                            changes.append(
                                f"[green]+ New instance: {service_name}/{inst_id[:12]}[/green]"
                            )

                        # Removed instances
                        for inst_id in prev_instances - curr_instances:
                            changes.append(
                                f"[red]- Removed instance: {service_name}/{inst_id[:12]}[/red]"
                            )

                        # Status changes
                        for instance in current_services[service_name]:
                            prev_inst = next(
                                (
                                    i
                                    for i in previous_state[service_name]
                                    if i.instance_id == instance.instance_id
                                ),
                                None,
                            )
                            if prev_inst and prev_inst.status != instance.status:
                                changes.append(
                                    f"[yellow]~ Status change: {service_name}/{instance.instance_id[:12]} "
                                    f"{prev_inst.status} → {instance.status}[/yellow]"
                                )

                # Display changes
                if changes:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    self.console.print(f"\n[dim]{timestamp}[/dim] Changes detected:")
                    for change in changes:
                        self.console.print(f"  {change}")

                    # Show updated summary
                    self.console.print("\nCurrent state:")
                    self.render_service_list(current_services)

                previous_state = current_services
                await asyncio.sleep(interval)

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Watch mode stopped[/yellow]")

    async def get_service_details(self, service_name: str) -> None:
        """Get detailed information about a specific service."""
        instances = await self.discovery.discover(service_name)

        if not instances:
            self.console.print(f"[red]Service '{service_name}' not found[/red]")
            return

        # Service overview
        panel = Panel(
            f"Service: [bold]{service_name}[/bold]\n"
            f"Total Instances: {len(instances)}\n"
            f"Active Instances: {sum(1 for i in instances if i.status == ServiceStatus.ACTIVE)}",
            title="Service Details",
            border_style="cyan",
        )
        self.console.print(panel)

        # Instance details
        for instance in instances:
            self.console.print(f"\n[bold]Instance: {instance.instance_id}[/bold]")

            # Create details table
            table = Table(show_header=False)
            table.add_column("Property", style="cyan")
            table.add_column("Value")

            table.add_row("Status", str(instance.status))
            table.add_row("Endpoint", instance.endpoint)
            table.add_row("Version", instance.version)
            table.add_row("Started", instance.started_at)

            # Capabilities
            if instance.capabilities:
                table.add_row("Capabilities", ", ".join(instance.capabilities))

            # Health
            if instance.health:
                health_info = f"Score: {instance.health.score}%"
                if instance.health.message:
                    health_info += f" ({instance.health.message})"
                table.add_row("Health", health_info)

            # Metadata
            if instance.metadata:
                for key, value in instance.metadata.items():
                    if isinstance(value, dict):
                        value = json.dumps(value, indent=2)
                    table.add_row(f"Metadata.{key}", str(value))

            self.console.print(table)

    async def test_service_connectivity(self, service_name: str) -> None:
        """Test connectivity to a service by sending a ping."""
        instances = await self.discovery.discover(service_name)

        if not instances:
            self.console.print(f"[red]Service '{service_name}' not found[/red]")
            return

        self.console.print(
            f"[yellow]Testing connectivity to {len(instances)} instance(s)...[/yellow]"
        )

        for instance in instances:
            try:
                # Try to send a ping RPC
                start_time = asyncio.get_event_loop().time()
                response = await self.nats_adapter.request(
                    f"rpc.{service_name}.ping", b'{"ping": true}', timeout=2.0
                )
                latency = (asyncio.get_event_loop().time() - start_time) * 1000

                if response:
                    self.console.print(
                        f"[green]✓[/green] {instance.instance_id[:12]} responded in {latency:.2f}ms"
                    )
                else:
                    self.console.print(
                        f"[yellow]![/yellow] {instance.instance_id[:12]} empty response"
                    )
            except asyncio.TimeoutError:
                self.console.print(f"[red]✗[/red] {instance.instance_id[:12]} timeout")
            except Exception as e:
                self.console.print(f"[red]✗[/red] {instance.instance_id[:12]} error: {e}")


async def interactive_menu():
    """Run interactive service explorer menu."""
    console = Console()

    console.print("[bold blue]Service Discovery Explorer[/bold blue]")
    console.print("Explore and monitor registered services\n")

    # Create explorer
    explorer = ServiceExplorer()

    try:
        await explorer.connect()

        while True:
            # Menu options
            console.print("\n[bold]Options:[/bold]")
            console.print("1. List all services")
            console.print("2. Tree view")
            console.print("3. Detailed view")
            console.print("4. Watch for changes")
            console.print("5. Get service details")
            console.print("6. Test service connectivity")
            console.print("7. Apply filters")
            console.print("8. Export to JSON")
            console.print("9. Quit")

            choice = console.input("\n[cyan]Select option (1-9): [/cyan]")

            if choice == "1":
                services = await explorer.discover_all_services()
                explorer.render_service_list(services)

            elif choice == "2":
                services = await explorer.discover_all_services()
                explorer.render_service_tree(services)

            elif choice == "3":
                services = await explorer.discover_all_services()
                explorer.render_detailed_view(services)

            elif choice == "4":
                await explorer.watch_services()

            elif choice == "5":
                service_name = console.input("[cyan]Enter service name: [/cyan]")
                await explorer.get_service_details(service_name)

            elif choice == "6":
                service_name = console.input("[cyan]Enter service name to test: [/cyan]")
                await explorer.test_service_connectivity(service_name)

            elif choice == "7":
                # Filter configuration
                console.print("\n[bold]Configure Filters:[/bold]")
                name_pattern = console.input("Name pattern (or Enter for all): ")
                include_inactive = (
                    console.input("Include inactive services? (y/n): ").lower() == "y"
                )
                include_metadata = console.input("Include metadata? (y/n): ").lower() == "y"

                explorer.filter = ServiceFilter(
                    name_pattern=name_pattern or None,
                    include_inactive=include_inactive,
                    include_metadata=include_metadata,
                )
                console.print("[green]Filters updated[/green]")

            elif choice == "8":
                # Export to JSON
                services = await explorer.discover_all_services()
                export_data = {
                    "timestamp": datetime.now().isoformat(),
                    "services": {
                        name: [
                            {
                                "instance_id": inst.instance_id,
                                "status": inst.status.value,
                                "endpoint": inst.endpoint,
                                "version": inst.version,
                                "capabilities": inst.capabilities,
                                "metadata": inst.metadata,
                                "health": (
                                    {
                                        "score": inst.health.score,
                                        "message": inst.health.message,
                                        "last_check": inst.health.last_check,
                                    }
                                    if inst.health
                                    else None
                                ),
                            }
                            for inst in instances
                        ]
                        for name, instances in services.items()
                    },
                }

                filename = f"service_discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, "w") as f:
                    json.dump(export_data, f, indent=2)
                console.print(f"[green]Exported to {filename}[/green]")

            elif choice == "9":
                break

            else:
                console.print("[red]Invalid option[/red]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Explorer stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        if explorer.nats_adapter:
            await explorer.nats_adapter.disconnect()
        console.print("[green]Disconnected[/green]")


async def main():
    """Main entry point."""
    await interactive_menu()


if __name__ == "__main__":
    asyncio.run(main())
