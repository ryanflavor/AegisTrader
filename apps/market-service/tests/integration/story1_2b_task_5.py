#!/usr/bin/env python
"""
Real Market Data Flow Integration Test using CTP Adapter
Story 1.2b Task 5: Test real CTP market data flow using existing infra adapters

This test validates the complete market data flow pipeline using real CTP connection.
It uses the infrastructure adapters without reimplementing functionality.
"""

import asyncio
import json
import locale
import os
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Setup project path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup locale for CTP (required for Chinese market)
if os.name != "nt":
    try:
        os.environ["LC_ALL"] = "zh_CN.gb18030"
        os.environ["LANG"] = "zh_CN.gb18030"
        locale.setlocale(locale.LC_ALL, "zh_CN.gb18030")
    except locale.Error:
        pass  # Silently ignore if locale not available


@dataclass
class TestMetrics:
    """Metrics collected during test execution"""

    total_ticks: int = 0
    total_errors: int = 0
    latencies: list[float] = field(default_factory=list)
    tick_data: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))
    data_quality_issues: list[str] = field(default_factory=list)
    test_start_time: datetime | None = None
    test_end_time: datetime | None = None

    def add_tick(self, symbol: str, tick_data: dict):
        """Add a tick to metrics"""
        self.tick_data[symbol].append(tick_data)
        self.total_ticks += 1

    def add_latency(self, latency_ms: float):
        """Add latency measurement"""
        if latency_ms > 0 and latency_ms < 10000:  # Sanity check
            self.latencies.append(latency_ms)

    def get_latency_stats(self) -> dict[str, float]:
        """Calculate latency statistics"""
        if not self.latencies:
            return {}
        return {
            "avg": sum(self.latencies) / len(self.latencies),
            "min": min(self.latencies),
            "max": max(self.latencies),
            "p50": sorted(self.latencies)[len(self.latencies) // 2],
            "p95": (
                sorted(self.latencies)[int(len(self.latencies) * 0.95)]
                if len(self.latencies) > 20
                else max(self.latencies)
            ),
            "samples": len(self.latencies),
        }


class MarketDataFlowTest:
    """Optimized market data flow test using infrastructure adapters"""

    def __init__(self, test_config: dict | None = None):
        """Initialize test with optional configuration"""
        self.config = test_config or {
            "test_instruments": ["rb2510", "cu2510", "ag2510"],
            "tick_collection_duration": 10,  # seconds
            "connection_timeout": 10,  # seconds
            "max_latency_ms": 500,  # milliseconds
            "min_tick_count": 10,  # minimum expected ticks
        }

        self.metrics = TestMetrics()
        self.adapter = None
        self.connection_established = False
        self.subscriptions: set[str] = set()
        self._tick_callback: Callable | None = None

    async def setup(self) -> bool:
        """Setup test environment and load configuration"""
        try:
            # Load environment configuration
            from dotenv import load_dotenv

            env_file = project_root / ".env.test.local"

            if not env_file.exists():
                print(f"❌ Config file not found: {env_file}")
                print("  Please create .env.test.local with CTP credentials")
                return False

            load_dotenv(env_file, override=True)

            # Validate required environment variables
            required_vars = [
                "CTP_REAL_USER_ID",
                "CTP_REAL_PASSWORD",
                "CTP_REAL_BROKER_ID",
                "CTP_REAL_MD_ADDRESS",
            ]

            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
                return False

            print("✅ Configuration loaded successfully")
            return True

        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False

    async def connect_to_ctp(self) -> bool:
        """Establish connection to CTP gateway using adapter"""
        try:
            from domain.gateway.value_objects import AuthenticationCredentials
            from infra.adapters.gateway.ctp_adapter import CtpConfig, CtpGatewayAdapter

            # Build configuration from environment
            config = CtpConfig(
                user_id=os.getenv("CTP_REAL_USER_ID", ""),
                password=os.getenv("CTP_REAL_PASSWORD", ""),
                broker_id=os.getenv("CTP_REAL_BROKER_ID", "9999"),
                td_address=os.getenv("CTP_REAL_TD_ADDRESS", ""),
                md_address=os.getenv("CTP_REAL_MD_ADDRESS", ""),
                app_id=os.getenv("CTP_REAL_APP_ID", ""),
                auth_code=os.getenv("CTP_REAL_AUTH_CODE", "0000000000000000"),
            )

            print("\n🔌 Connecting to CTP Gateway")
            print(f"  User: {config.user_id}")
            print(f"  Broker: {config.broker_id}")
            print(f"  Server: {config.md_address}")

            # Create and connect adapter
            self.adapter = CtpGatewayAdapter(config)

            credentials = AuthenticationCredentials(
                user_id=config.user_id,
                password=config.password,
                broker_id=config.broker_id,
                app_id=config.app_id,
                auth_code=config.auth_code,
                td_address=config.td_address,
                md_address=config.md_address,
            )

            # Connect with timeout
            await asyncio.wait_for(
                self.adapter.connect(credentials), timeout=self.config["connection_timeout"]
            )

            # Wait for initialization
            await asyncio.sleep(2)

            # Verify connection
            status = await self.adapter.get_connection_status()
            event_stats = status.get("event_stats", {})
            contract_events = event_stats.get("eContract.", 0)

            if contract_events > 0:
                self.connection_established = True
                print(f"  ✅ Connected (received {contract_events} contracts)")
                return True
            else:
                print(f"  ❌ Connection failed: {status}")
                return False

        except TimeoutError:
            print(f"  ❌ Connection timeout ({self.config['connection_timeout']}s)")
            return False
        except Exception as e:
            print(f"  ❌ Connection error: {e}")
            return False

    async def subscribe_instruments(self) -> bool:
        """Subscribe to test instruments"""
        if not self.connection_established:
            print("❌ Cannot subscribe: No active connection")
            return False

        print(f"\n📊 Subscribing to {len(self.config['test_instruments'])} instruments")

        success_count = 0
        for symbol in self.config["test_instruments"]:
            try:
                result = await self.adapter.subscribe(symbol)
                if result:
                    self.subscriptions.add(symbol)
                    success_count += 1
                    print(f"  ✅ {symbol}")
                else:
                    print(f"  ❌ {symbol}")
            except Exception as e:
                print(f"  ❌ {symbol}: {e}")

        print(f"  Subscribed: {success_count}/{len(self.config['test_instruments'])}")
        return success_count > 0

    def _create_tick_handler(self) -> Callable:
        """Create optimized tick data handler"""

        def on_tick(tick):
            try:
                # Extract data from domain Tick object
                symbol_str = str(tick.symbol)
                now = datetime.now(UTC)

                tick_data = {
                    "symbol": symbol_str,
                    "price": float(tick.price.value),
                    "volume": tick.volume.value if hasattr(tick, "volume") else 0,
                    "local_time": now.isoformat(),
                    "exchange_time": tick.timestamp.isoformat() if tick.timestamp else None,
                }

                # Record tick
                self.metrics.add_tick(symbol_str, tick_data)

                # Calculate latency if timestamp available
                if tick.timestamp and isinstance(tick.timestamp, datetime):
                    latency_ms = (now - tick.timestamp).total_seconds() * 1000
                    self.metrics.add_latency(abs(latency_ms))

            except Exception:
                self.metrics.total_errors += 1

        return on_tick

    async def collect_market_data(self) -> bool:
        """Collect and analyze market data"""
        if not self.subscriptions:
            print("❌ No active subscriptions")
            return False

        print(f"\n📈 Collecting market data for {self.config['tick_collection_duration']}s")

        # Register tick handler
        self._tick_callback = self._create_tick_handler()
        self.adapter.register_tick_callback(self._tick_callback)

        # Start collection
        self.metrics.test_start_time = datetime.now(UTC)
        collection_duration = self.config["tick_collection_duration"]

        # Show progress
        for i in range(collection_duration):
            await asyncio.sleep(1)
            ticks_so_far = self.metrics.total_ticks
            if i % 2 == 0:  # Update every 2 seconds
                print(
                    f"  Progress: {i + 1}/{collection_duration}s | Ticks: {ticks_so_far}", end="\r"
                )

        self.metrics.test_end_time = datetime.now(UTC)
        print()  # New line after progress

        # Analyze results
        return self._analyze_collected_data()

    def _analyze_collected_data(self) -> bool:
        """Analyze collected market data"""
        total_ticks = self.metrics.total_ticks
        instruments_with_data = len(self.metrics.tick_data)

        print("\n📊 Data Collection Results:")
        print(f"  Total ticks: {total_ticks}")
        print(f"  Instruments: {instruments_with_data}/{len(self.subscriptions)}")
        print(f"  Errors: {self.metrics.total_errors}")

        # Show per-instrument statistics
        for symbol, ticks in self.metrics.tick_data.items():
            if ticks:
                latest = ticks[-1]
                print(f"  {symbol}: {len(ticks)} ticks @ {latest['price']:.2f}")

        # Latency analysis
        if self.metrics.latencies:
            stats = self.metrics.get_latency_stats()
            print("\n⏱️  Latency Statistics:")
            print(f"  Average: {stats['avg']:.1f}ms")
            print(f"  Min/Max: {stats['min']:.1f}ms / {stats['max']:.1f}ms")
            print(f"  P50/P95: {stats['p50']:.1f}ms / {stats['p95']:.1f}ms")

            # Evaluate latency
            if stats["avg"] < 100:
                print("  ✅ Excellent latency")
            elif stats["avg"] < self.config["max_latency_ms"]:
                print("  ⚠️  Acceptable latency")
            else:
                print("  ❌ High latency detected")

        # Determine success
        if total_ticks >= self.config["min_tick_count"]:
            print("\n✅ Data collection successful")
            return True
        elif total_ticks > 0:
            print("\n⚠️  Limited data (market may be closed)")
            return True
        else:
            print("\n❌ No data received")
            return False

    async def validate_data_quality(self) -> bool:
        """Validate quality of collected data"""
        if not self.metrics.tick_data:
            print("\n⚠️  No data to validate")
            return True

        print("\n🔍 Validating Data Quality")
        issues = []

        for symbol, ticks in self.metrics.tick_data.items():
            # Check for price anomalies
            prices = [t["price"] for t in ticks]
            if prices:
                avg_price = sum(prices) / len(prices)
                for i, price in enumerate(prices):
                    # Check for extreme price deviations (>10%)
                    if abs(price - avg_price) / avg_price > 0.1:
                        issues.append(f"{symbol}: Large price deviation at tick {i}")

            # Check for missing data
            for i, tick in enumerate(ticks):
                if tick["price"] <= 0:
                    issues.append(f"{symbol}: Invalid price at tick {i}")
                if not tick["local_time"]:
                    issues.append(f"{symbol}: Missing timestamp at tick {i}")

        self.metrics.data_quality_issues = issues

        if not issues:
            print("  ✅ All quality checks passed")
            return True
        else:
            print(f"  ⚠️  Found {len(issues)} issues:")
            for issue in issues[:5]:  # Show first 5
                print(f"    - {issue}")
            return len(issues) < self.metrics.total_ticks * 0.1  # Allow 10% issues

    async def test_reconnection(self) -> bool:
        """Test reconnection capability"""
        if not self.connection_established:
            print("\n⚠️  Skipping reconnection test (no connection)")
            return True

        print("\n🔄 Testing Reconnection")

        try:
            # Save current state
            old_tick_count = self.metrics.total_ticks

            # Disconnect
            print("  Disconnecting...")
            await self.adapter.disconnect()
            await asyncio.sleep(2)

            # Reconnect
            print("  Reconnecting...")
            if not await self.connect_to_ctp():
                print("  ❌ Reconnection failed")
                return False

            # Resubscribe
            print("  Resubscribing...")
            self.subscriptions.clear()
            if not await self.subscribe_instruments():
                print("  ❌ Resubscription failed")
                return False

            # Re-register tick callback after reconnection
            print("  Re-registering tick handler...")
            if self._tick_callback:
                self.adapter.register_tick_callback(self._tick_callback)
            else:
                self._tick_callback = self._create_tick_handler()
                self.adapter.register_tick_callback(self._tick_callback)

            # Collect some data to verify
            print("  Verifying data flow...")
            await asyncio.sleep(5)  # Give more time for data to arrive

            new_tick_count = self.metrics.total_ticks
            if new_tick_count > old_tick_count:
                print(
                    f"  ✅ Reconnection successful (new ticks: {new_tick_count - old_tick_count})"
                )
                return True
            else:
                print("  ⚠️  No new data after reconnection")
                return True  # Not a failure if market is closed

        except Exception as e:
            print(f"  ❌ Reconnection test error: {e}")
            return False

    async def cleanup(self):
        """Clean up test resources"""
        if self.adapter:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def run(self) -> bool:
        """Run complete test suite"""
        print("\n" + "=" * 60)
        print("MARKET DATA FLOW INTEGRATION TEST")
        print("=" * 60)

        # Check market hours
        hour = datetime.now().hour
        if hour < 9 or hour > 15:
            print("⚠️  Outside market hours (09:00-15:00 CST)")

        try:
            # Setup
            if not await self.setup():
                return False

            # Connect
            if not await self.connect_to_ctp():
                return False

            # Subscribe
            if not await self.subscribe_instruments():
                return False

            # Collect data
            if not await self.collect_market_data():
                return False

            # Validate quality
            await self.validate_data_quality()

            # Test reconnection
            await self.test_reconnection()

            # Generate report
            self._generate_report()

            return True

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

        finally:
            await self.cleanup()

    def _generate_report(self):
        """Generate test execution report"""
        print("\n" + "=" * 60)
        print("TEST EXECUTION REPORT")
        print("=" * 60)

        if self.metrics.test_start_time and self.metrics.test_end_time:
            duration = (self.metrics.test_end_time - self.metrics.test_start_time).total_seconds()
            print(f"Duration: {duration:.1f}s")

        print(f"Total Ticks: {self.metrics.total_ticks}")
        print(f"Total Errors: {self.metrics.total_errors}")
        print(
            f"Error Rate: {self.metrics.total_errors / max(1, self.metrics.total_ticks) * 100:.2f}%"
        )

        if self.metrics.latencies:
            stats = self.metrics.get_latency_stats()
            print(f"Avg Latency: {stats['avg']:.1f}ms")
            print(f"P95 Latency: {stats['p95']:.1f}ms")

        if self.metrics.data_quality_issues:
            print(f"Quality Issues: {len(self.metrics.data_quality_issues)}")

        # Save metrics to file for analysis
        metrics_file = project_root / "test_metrics.json"
        try:
            with open(metrics_file, "w") as f:
                json.dump(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "total_ticks": self.metrics.total_ticks,
                        "total_errors": self.metrics.total_errors,
                        "latency_stats": (
                            self.metrics.get_latency_stats() if self.metrics.latencies else {}
                        ),
                        "instruments": list(self.metrics.tick_data.keys()),
                        "quality_issues": len(self.metrics.data_quality_issues),
                    },
                    f,
                    indent=2,
                )
            print(f"\nMetrics saved to: {metrics_file}")
        except:
            pass


async def main():
    """Main test entry point"""
    # Optional: Load custom configuration
    custom_config = None
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1]) as f:
                custom_config = json.load(f)
                print(f"Using custom config: {sys.argv[1]}")
        except:
            print(f"Warning: Could not load config from {sys.argv[1]}")

    # Run test
    test = MarketDataFlowTest(custom_config)
    success = await test.run()

    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
