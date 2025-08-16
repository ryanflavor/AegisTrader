#!/usr/bin/env python
"""
直接测试真实CTP账户连接（不使用pytest）
Direct test of real CTP account connection (without pytest)
"""

import asyncio
import locale
import os
import sys
import time
from pathlib import Path

# Setup project path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env.test.local
from dotenv import load_dotenv

env_file = project_root / ".env.test.local"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    print(f"❌ Environment file not found: {env_file}")
    sys.exit(1)

# CTP requires Chinese GB18030 locale
print("\n📋 Setting locale for CTP...")
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
            print("⚠️  zh_CN.gb18030 locale not available. Tests may fail.")
            print("   Install with: sudo locale-gen zh_CN.GB18030")


def test_ctp_import():
    """测试CTP模块是否可以导入"""
    print("\n🔧 Testing CTP module import...")
    try:
        from vnpy_ctp.api.vnctpmd import MdApi
        from vnpy_ctp.api.vnctptd import TdApi

        print("✅ vnpy_ctp module imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import vnpy_ctp: {e}")
        return False


def test_ctp_adapter():
    """测试CTP适配器"""
    print("\n🔧 Testing CTP Adapter...")
    try:
        from infra.gateway.ctp_adapter import CtpConfig, CtpGatewayAdapter

        # Create config from environment
        config = CtpConfig(
            user_id=os.getenv("CTP_REAL_USER_ID", ""),
            password=os.getenv("CTP_REAL_PASSWORD", ""),
            broker_id=os.getenv("CTP_REAL_BROKER_ID", ""),
            td_address=os.getenv("CTP_REAL_TD_ADDRESS", ""),
            md_address=os.getenv("CTP_REAL_MD_ADDRESS", ""),
            app_id=os.getenv("CTP_REAL_APP_ID", "client_vntech_2.0"),
            auth_code=os.getenv("CTP_REAL_AUTH_CODE", "52TMMTN41F3KFR83"),
        )

        print(f"  User ID: {config.user_id}")
        print(f"  Broker ID: {config.broker_id}")
        print(f"  TD Address: {config.td_address}")
        print(f"  MD Address: {config.md_address}")

        # Create adapter
        adapter = CtpGatewayAdapter(config)
        print("✅ CTP Adapter created successfully")
        return True, adapter, config
    except Exception as e:
        print(f"❌ Failed to create CTP Adapter: {e}")
        import traceback

        traceback.print_exc()
        return False, None, None


async def test_ctp_connection(adapter):
    """测试CTP连接"""
    print("\n🔧 Testing CTP Connection...")
    try:
        # Connect
        print("  Connecting to CTP...")
        await adapter.connect()

        # Wait for connection
        print("  Waiting for connection (5 seconds)...")
        await asyncio.sleep(5)

        # Check status
        status = await adapter.get_connection_status()
        print("\n📊 Connection Status:")
        print(f"  Connected: {status.get('is_connected', False)}")
        print(f"  TD Connected: {status.get('td_connected', False)}")
        print(f"  MD Connected: {status.get('md_connected', False)}")
        print(f"  Authenticated: {status.get('is_authenticated', False)}")

        if status.get("is_connected"):
            print("✅ Successfully connected to CTP")

            # Try subscribing to a symbol
            print("\n📈 Subscribing to market data...")
            await adapter.subscribe(["rb2501"])  # 螺纹钢主力
            await asyncio.sleep(2)
            print("✅ Subscription request sent")

            return True
        else:
            print("❌ Failed to connect to CTP")
            return False

    except Exception as e:
        print(f"❌ Connection error: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Always disconnect
        print("\n🔌 Disconnecting...")
        await adapter.disconnect()
        print("✅ Disconnected")


async def test_direct_ctp_api():
    """直接测试CTP API（不通过适配器）"""
    print("\n🔧 Testing Direct CTP API...")

    try:
        from vnpy_ctp.api.vnctpmd import MdApi

        class TestMdApi(MdApi):
            """Test Market Data API"""

            def __init__(self):
                super().__init__()
                self.connected = False
                self.logged_in = False
                self.error = None

            def onFrontConnected(self):
                print("  ✅ MD Front Connected")
                self.connected = True

            def onRspUserLogin(self, data, error, reqid, last):
                if error and error["ErrorID"] != 0:
                    print(f"  ❌ MD Login Error: {error}")
                    self.error = error
                else:
                    print("  ✅ MD Login Success")
                    self.logged_in = True
                    if data:
                        print(f"    Trading Day: {data.get('TradingDay')}")

            def onRtnDepthMarketData(self, data):
                print(f"  📊 Tick: {data.get('InstrumentID')} - {data.get('LastPrice')}")

        # Create MD API
        md_api = TestMdApi()

        # Clean temp directory
        import shutil

        temp_dir = "/tmp/test_ctp_md_direct"
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

        # Initialize
        md_api.createFtdcMdApi(temp_dir)
        md_api.registerFront(os.getenv("CTP_REAL_MD_ADDRESS"))
        print(f"  Connecting to: {os.getenv('CTP_REAL_MD_ADDRESS')}")
        md_api.init()

        # Wait for connection
        print("  Waiting for connection...")
        time.sleep(3)

        if md_api.connected:
            # Login
            req = {
                "BrokerID": os.getenv("CTP_REAL_BROKER_ID"),
                "UserID": os.getenv("CTP_REAL_USER_ID"),
                "Password": os.getenv("CTP_REAL_PASSWORD"),
            }
            print(f"  Logging in as: {req['UserID']}")
            md_api.reqUserLogin(req, 1)
            time.sleep(3)

            if md_api.logged_in:
                print("✅ Direct CTP API test successful")
                return True
            else:
                print(f"❌ Login failed: {md_api.error}")
                return False
        else:
            print("❌ Connection failed")
            return False

    except Exception as e:
        print(f"❌ Direct API test error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("=" * 60)
    print("🚀 Real CTP Account Test (Without pytest)")
    print("=" * 60)

    # Check environment
    print("\n📋 Environment Check:")
    user_id = os.getenv("CTP_REAL_USER_ID")
    if not user_id:
        print("❌ CTP_REAL_USER_ID not set in .env.test.local")
        return

    print(f"✅ CTP Account: {user_id}")

    # Test import
    if not test_ctp_import():
        print("\n⚠️  Cannot proceed without vnpy_ctp module")
        return

    # Test direct API first (simpler, less dependencies)
    print("\n" + "=" * 40)
    print("Test 1: Direct CTP API")
    print("=" * 40)
    await test_direct_ctp_api()

    # Test adapter
    print("\n" + "=" * 40)
    print("Test 2: CTP Adapter")
    print("=" * 40)
    success, adapter, config = test_ctp_adapter()

    if success and adapter:
        # Test connection
        await test_ctp_connection(adapter)

    print("\n" + "=" * 60)
    print("✅ Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
