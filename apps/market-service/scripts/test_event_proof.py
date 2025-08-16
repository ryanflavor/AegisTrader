#!/usr/bin/env python
"""
Prove that vnpy events are being triggered correctly
"""

import asyncio
import locale
import os
import sys
from datetime import datetime
from pathlib import Path

# Setup project path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv

env_file = project_root / ".env.test.local"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"✅ Loaded CTP credentials from {env_file}")

# Set Chinese locale for CTP
if os.name != "nt":
    try:
        os.environ["LC_ALL"] = "zh_CN.gb18030"
        os.environ["LANG"] = "zh_CN.gb18030"
        locale.setlocale(locale.LC_ALL, "zh_CN.gb18030")
        print("✅ Locale set to zh_CN.gb18030")
    except locale.Error:
        try:
            os.environ["LC_ALL"] = "zh_CN.GB18030"
            os.environ["LANG"] = "zh_CN.GB18030"
            locale.setlocale(locale.LC_ALL, "zh_CN.GB18030")
            print("✅ Locale set to zh_CN.GB18030")
        except locale.Error:
            print("⚠️  zh_CN.gb18030 locale not available")


async def prove_events():
    """Prove that events are triggering"""
    print("\n" + "=" * 70)
    print("🔬 PROVING VNPY EVENTS ARE TRIGGERED")
    print("=" * 70)

    # Import vnpy and create event engine directly
    from vnpy.event import Event, EventEngine
    from vnpy.trader.event import (
        EVENT_CONTRACT,
        EVENT_LOG,
        EVENT_TICK,
    )

    # Create event engine
    event_engine = EventEngine()
    event_engine.start()
    print("✅ EventEngine started")

    # Track all events
    events_captured = {
        "EVENT_LOG": [],
        "EVENT_TICK": [],
        "EVENT_CONTRACT": [],
        "EVENT_ACCOUNT": [],
        "EVENT_POSITION": [],
        "OTHER": [],
    }

    # Register handlers for all event types
    def on_log(event: Event):
        msg = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] LOG: {event.data}"
        events_captured["EVENT_LOG"].append(msg)
        print(f"🔵 {msg}")

    def on_tick(event: Event):
        msg = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] TICK: {event.data}"
        events_captured["EVENT_TICK"].append(msg)
        print(f"📊 {msg}")

    def on_contract(event: Event):
        msg = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] CONTRACT: {event.data}"
        events_captured["EVENT_CONTRACT"].append(msg)
        print(f"📝 {msg}")

    def on_any(event: Event):
        if event.type not in [EVENT_LOG, EVENT_TICK, EVENT_CONTRACT]:
            msg = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {event.type}: {event.data}"
            events_captured["OTHER"].append(msg)
            print(f"🟡 {msg}")

    # Register all handlers
    event_engine.register(EVENT_LOG, on_log)
    event_engine.register(EVENT_TICK, on_tick)
    event_engine.register(EVENT_CONTRACT, on_contract)
    event_engine.register_general(on_any)  # Catch all other events

    print("\n📡 Event handlers registered:")
    print(f"   - EVENT_LOG: {EVENT_LOG}")
    print(f"   - EVENT_TICK: {EVENT_TICK}")
    print(f"   - EVENT_CONTRACT: {EVENT_CONTRACT}")

    # Now create CTP gateway with this event engine
    print("\n🔌 Creating CTP Gateway...")
    from vnpy.trader.setting import SETTINGS
    from vnpy_ctp import CtpGateway

    # Configure settings
    SETTINGS["log.active"] = True
    SETTINGS["log.level"] = 10  # DEBUG level
    SETTINGS["log.console"] = True

    # Create gateway with our event engine
    gateway = CtpGateway(event_engine, "CTP")

    # Connect to CTP
    setting = {
        "用户名": os.getenv("CTP_REAL_USER_ID", ""),
        "密码": os.getenv("CTP_REAL_PASSWORD", ""),
        "经纪商代码": os.getenv("CTP_REAL_BROKER_ID", ""),
        "交易服务器": os.getenv("CTP_REAL_TD_ADDRESS", ""),
        "行情服务器": os.getenv("CTP_REAL_MD_ADDRESS", ""),
        "产品名称": os.getenv("CTP_REAL_APP_ID", "client_vntech_2.0"),
        "授权编码": os.getenv("CTP_REAL_AUTH_CODE", "52TMMTN41F3KFR83"),
    }

    print("\n🚀 Connecting to CTP...")
    print(f"   User: {setting['用户名']}")
    print(f"   Broker: {setting['经纪商代码']}")

    gateway.connect(setting)

    # Wait and collect events
    print("\n⏳ Waiting for events (30 seconds)...")
    await asyncio.sleep(30)

    # Subscribe to test tick events
    print("\n📊 Subscribing to rb2501...")
    req = gateway.create_subscribe_request("rb2501", "SHFE")
    gateway.subscribe(req)

    # Wait for tick data
    print("⏳ Waiting for tick data (10 seconds)...")
    await asyncio.sleep(10)

    # Stop gateway
    print("\n🛑 Stopping gateway...")
    gateway.close()
    event_engine.stop()

    # Print summary
    print("\n" + "=" * 70)
    print("📊 EVENT CAPTURE SUMMARY")
    print("=" * 70)

    total_events = 0
    for event_type, events in events_captured.items():
        count = len(events)
        total_events += count
        if count > 0:
            print(f"\n{event_type}: {count} events")
            # Show first 3 events of each type
            for evt in events[:3]:
                print(f"  {evt}")
            if count > 3:
                print(f"  ... and {count - 3} more")

    print("\n" + "=" * 70)
    print(f"🎯 TOTAL EVENTS CAPTURED: {total_events}")
    print("=" * 70)

    if total_events > 0:
        print("\n✅ PROOF: Events ARE being triggered!")
    else:
        print("\n❌ No events captured - something is wrong")

    return total_events > 0


async def main():
    """Main entry point"""
    success = await prove_events()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
