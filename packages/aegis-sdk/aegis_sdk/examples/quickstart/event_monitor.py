#!/usr/bin/env python3
"""
Event Stream Monitor Client

This client monitors and displays event streams in real-time,
allowing filtering by topic, event type, and subscription mode.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from aegis_sdk.developer import quick_setup
from aegis_sdk.domain.enums import SubscriptionMode


class EventType(str, Enum):
    """Event types to monitor."""

    ORDER_CREATED = "orders.created"
    ORDER_UPDATED = "orders.updated"
    ORDER_COMPLETED = "orders.completed"
    ORDER_CANCELLED = "orders.cancelled"
    PAYMENT_PROCESSED = "payments.processed"
    PAYMENT_FAILED = "payments.failed"
    INVENTORY_UPDATED = "inventory.updated"
    SERVICE_STATUS = "services.status"
    SYSTEM_HEALTH = "system.health"
    ALL = "*"


class EventFilter(BaseModel):
    """Filters for event monitoring."""

    topics: list[str] = Field(default_factory=lambda: ["*"])
    event_types: list[EventType] = Field(default_factory=lambda: [EventType.ALL])
    service_filter: str | None = Field(default=None)
    max_events: int = Field(default=100)
    show_payloads: bool = Field(default=True)


@dataclass
class EventMetrics:
    """Metrics for monitored events."""

    total_events: int = 0
    events_per_second: float = 0.0
    events_by_type: dict[str, int] = field(default_factory=dict)
    events_by_service: dict[str, int] = field(default_factory=dict)
    last_event_time: datetime | None = None
    start_time: datetime = field(default_factory=datetime.now)


@dataclass
class MonitoredEvent:
    """A captured event with metadata."""

    timestamp: datetime
    topic: str
    event_type: str
    service_name: str
    payload: dict[str, Any]
    sequence: int
    size_bytes: int


class EventStreamMonitor:
    """
    Event stream monitoring client following DDD principles.

    This is an EXTERNAL CLIENT pattern - monitoring events
    without being a service itself.
    """

    def __init__(self, filter_config: EventFilter):
        """Initialize the event monitor."""
        self.filter = filter_config
        self.events: list[MonitoredEvent] = []
        self.metrics = EventMetrics()
        self.console = Console()
        self.running = False
        self.sequence_counter = 0
        self.subscriptions: dict[str, Any] = {}

    async def connect(self) -> None:
        """Connect to NATS and set up subscriptions."""
        # Use quick_setup for external client pattern
        self.client = await quick_setup("event-monitor", as_client=True)

        # Subscribe to filtered topics
        for topic in self.filter.topics:
            if topic == "*":
                # Subscribe to all events with wildcard
                sub = await self.client.subscribe(
                    "*.>", callback=self._handle_event, mode=SubscriptionMode.BROADCAST
                )
                self.subscriptions["all"] = sub
            else:
                # Subscribe to specific topic
                sub = await self.client.subscribe(
                    topic, callback=self._handle_event, mode=SubscriptionMode.BROADCAST
                )
                self.subscriptions[topic] = sub

        self.console.print(
            f"[green]Connected to event streams. Monitoring {len(self.subscriptions)} subscription(s)[/green]"
        )

    async def _handle_event(self, msg: Any) -> None:
        """Handle incoming event messages."""
        try:
            # Parse event data
            event_data = json.loads(msg.data.decode())

            # Extract metadata
            topic = msg.subject
            event_type = event_data.get("type", "unknown")
            service_name = event_data.get("service", "unknown")

            # Apply filters
            if not self._should_process_event(event_type, service_name):
                return

            # Create monitored event
            self.sequence_counter += 1
            event = MonitoredEvent(
                timestamp=datetime.now(),
                topic=topic,
                event_type=event_type,
                service_name=service_name,
                payload=event_data.get("data", {}),
                sequence=self.sequence_counter,
                size_bytes=len(msg.data),
            )

            # Update metrics
            self._update_metrics(event)

            # Store event (with max limit)
            self.events.append(event)
            if len(self.events) > self.filter.max_events:
                self.events.pop(0)

        except Exception as e:
            self.console.print(f"[red]Error processing event: {e}[/red]")

    def _should_process_event(self, event_type: str, service_name: str) -> bool:
        """Check if event passes filters."""
        # Check event type filter
        if EventType.ALL not in self.filter.event_types:
            if event_type not in [et.value for et in self.filter.event_types]:
                return False

        # Check service filter
        if self.filter.service_filter:
            if service_name != self.filter.service_filter:
                return False

        return True

    def _update_metrics(self, event: MonitoredEvent) -> None:
        """Update metrics based on event."""
        self.metrics.total_events += 1
        self.metrics.last_event_time = event.timestamp

        # Update event type counts
        if event.event_type not in self.metrics.events_by_type:
            self.metrics.events_by_type[event.event_type] = 0
        self.metrics.events_by_type[event.event_type] += 1

        # Update service counts
        if event.service_name not in self.metrics.events_by_service:
            self.metrics.events_by_service[event.service_name] = 0
        self.metrics.events_by_service[event.service_name] += 1

        # Calculate events per second
        elapsed = (datetime.now() - self.metrics.start_time).total_seconds()
        if elapsed > 0:
            self.metrics.events_per_second = self.metrics.total_events / elapsed

    def create_dashboard(self) -> Layout:
        """Create the monitoring dashboard layout."""
        layout = Layout()

        # Split into header, main content, and footer
        layout.split_column(
            Layout(name="header", size=3), Layout(name="main"), Layout(name="footer", size=4)
        )

        # Split main into events and metrics
        layout["main"].split_row(Layout(name="events", ratio=2), Layout(name="metrics", ratio=1))

        return layout

    def render_header(self) -> Panel:
        """Render the header panel."""
        status = "[green]● MONITORING[/green]" if self.running else "[red]● STOPPED[/red]"
        filters = f"Topics: {', '.join(self.filter.topics)} | "
        filters += f"Types: {', '.join([et.value for et in self.filter.event_types])}"

        return Panel(f"{status} | {filters}", title="Event Stream Monitor", border_style="blue")

    def render_events_table(self) -> Panel:
        """Render the events table."""
        table = Table(title="Recent Events", show_header=True, header_style="bold magenta")

        table.add_column("Seq", style="dim", width=6)
        table.add_column("Time", style="cyan", width=12)
        table.add_column("Topic", style="yellow")
        table.add_column("Type", style="green")
        table.add_column("Service", style="blue")

        if self.filter.show_payloads:
            table.add_column("Payload", style="white")

        # Show most recent events first
        for event in reversed(self.events[-20:]):  # Show last 20 events
            time_str = event.timestamp.strftime("%H:%M:%S.%f")[:-3]

            row = [str(event.sequence), time_str, event.topic, event.event_type, event.service_name]

            if self.filter.show_payloads:
                payload_str = json.dumps(event.payload, indent=None)
                if len(payload_str) > 50:
                    payload_str = payload_str[:47] + "..."
                row.append(payload_str)

            table.add_row(*row)

        return Panel(table, title="Event Stream", border_style="green")

    def render_metrics(self) -> Panel:
        """Render the metrics panel."""
        table = Table(show_header=False)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="white")

        # Overall metrics
        table.add_row("Total Events", str(self.metrics.total_events))
        table.add_row("Events/sec", f"{self.metrics.events_per_second:.2f}")

        if self.metrics.last_event_time:
            last_ago = (datetime.now() - self.metrics.last_event_time).total_seconds()
            table.add_row("Last Event", f"{last_ago:.1f}s ago")

        table.add_row("", "")  # Separator

        # Top event types
        table.add_row("Top Event Types", "")
        for event_type, count in sorted(
            self.metrics.events_by_type.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            table.add_row(f"  {event_type}", str(count))

        table.add_row("", "")  # Separator

        # Top services
        table.add_row("Top Services", "")
        for service, count in sorted(
            self.metrics.events_by_service.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            table.add_row(f"  {service}", str(count))

        return Panel(table, title="Metrics", border_style="blue")

    def render_footer(self) -> Panel:
        """Render the footer with controls."""
        controls = [
            "[q] Quit",
            "[c] Clear Events",
            "[p] Toggle Payloads",
            "[f] Change Filters",
            "[s] Save Events",
        ]

        return Panel(" | ".join(controls), title="Controls", border_style="dim")

    async def run_interactive(self) -> None:
        """Run the interactive monitoring dashboard."""
        self.running = True
        layout = self.create_dashboard()

        with Live(layout, refresh_per_second=2, screen=True) as live:
            while self.running:
                # Update dashboard
                layout["header"].update(self.render_header())
                layout["events"].update(self.render_events_table())
                layout["metrics"].update(self.render_metrics())
                layout["footer"].update(self.render_footer())

                # Check for keyboard input (simplified for example)
                await asyncio.sleep(0.5)

                # In a real implementation, would handle keyboard input here
                # For now, just run for a fixed duration
                if self.metrics.total_events > 100:
                    self.running = False

    async def export_events(self, filename: str) -> None:
        """Export captured events to a file."""
        export_data = {
            "metadata": {
                "export_time": datetime.now().isoformat(),
                "total_events": len(self.events),
                "filters": self.filter.model_dump(),
            },
            "metrics": {
                "total_events": self.metrics.total_events,
                "events_per_second": self.metrics.events_per_second,
                "events_by_type": self.metrics.events_by_type,
                "events_by_service": self.metrics.events_by_service,
            },
            "events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "topic": event.topic,
                    "event_type": event.event_type,
                    "service_name": event.service_name,
                    "payload": event.payload,
                    "sequence": event.sequence,
                    "size_bytes": event.size_bytes,
                }
                for event in self.events
            ],
        }

        with open(filename, "w") as f:
            json.dump(export_data, f, indent=2)

        self.console.print(f"[green]Exported {len(self.events)} events to {filename}[/green]")


async def main():
    """Main entry point for the event monitor."""
    console = Console()

    console.print("[bold blue]Event Stream Monitor[/bold blue]")
    console.print("Monitor and analyze event streams in real-time\n")

    # Configure filters
    filter_config = EventFilter(
        topics=["orders.*", "payments.*", "services.*"],
        event_types=[EventType.ALL],
        max_events=1000,
        show_payloads=True,
    )

    # Create and connect monitor
    monitor = EventStreamMonitor(filter_config)

    try:
        await monitor.connect()

        # Run interactive dashboard
        console.print("[yellow]Starting event monitoring dashboard...[/yellow]")
        await monitor.run_interactive()

        # Export events on exit
        await monitor.export_events("event_monitor_export.json")

    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        # Clean up
        for sub in monitor.subscriptions.values():
            await sub.unsubscribe()
        console.print("[green]Monitor disconnected[/green]")


if __name__ == "__main__":
    asyncio.run(main())
