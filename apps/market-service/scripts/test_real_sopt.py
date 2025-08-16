#!/usr/bin/env python
"""
直接测试真实SOPT账户连接（不使用pytest）
Direct test of real SOPT account connection (without pytest)
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

# SOPT requires Chinese GB18030 locale
print("\n📋 Setting locale for SOPT...")
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


def test_sopt_import():
    """测试SOPT模块是否可以导入"""
    print("\n🔧 Testing SOPT module import...")
    try:
        from vnpy_sopt.api.vnsoptmd import MdApi
        from vnpy_sopt.api.vnsopttd import TdApi

        print("✅ vnpy_sopt module imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import vnpy_sopt: {e}")
        return False


def test_sopt_adapter():
    """测试SOPT适配器"""
    print("\n🔧 Testing SOPT Adapter...")
    try:
        from infra.gateway.sopt_adapter import SoptConfig, SoptGatewayAdapter

        # Create config from environment
        config = SoptConfig(
            user_id=os.getenv("SOPT_REAL_USER_ID", ""),
            password=os.getenv("SOPT_REAL_PASSWORD", ""),
            broker_id=os.getenv("SOPT_REAL_BROKER_ID", ""),
            td_address=os.getenv("SOPT_REAL_TD_ADDRESS", ""),
            md_address=os.getenv("SOPT_REAL_MD_ADDRESS", ""),
            app_id=os.getenv("SOPT_REAL_APP_ID", "client_vntech_2.0"),
            auth_code=os.getenv("SOPT_REAL_AUTH_CODE", "52TMMTN41F3KFR83"),
        )

        print(f"  User ID: {config.user_id}")
        print(f"  Broker ID: {config.broker_id}")
        print(f"  TD Address: {config.td_address}")
        print(f"  MD Address: {config.md_address}")

        # Create adapter
        adapter = SoptGatewayAdapter(config)
        print("✅ SOPT Adapter created successfully")
        return True, adapter, config
    except Exception as e:
        print(f"❌ Failed to create SOPT Adapter: {e}")
        import traceback

        traceback.print_exc()
        return False, None, None


async def test_sopt_connection(adapter):
    """测试SOPT连接"""
    print("\n🔧 Testing SOPT Connection...")
    try:
        # Connect
        print("  Connecting to SOPT...")
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
            print("✅ Successfully connected to SOPT")

            # Try subscribing to a symbol
            print("\n📈 Subscribing to market data...")
            await adapter.subscribe(["510050.SSE"])  # 50ETF期权
            await asyncio.sleep(2)
            print("✅ Subscription request sent")

            return True
        else:
            print("❌ Failed to connect to SOPT")
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


async def test_direct_sopt_api():
    """直接测试SOPT API（不通过适配器）"""
    print("\n🔧 Testing Direct SOPT API...")

    try:
        from vnpy_sopt.api.vnsoptmd import MdApi

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

        temp_dir = "/tmp/test_sopt_md_direct"
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

        # Initialize
        md_api.createFtdcMdApi(temp_dir)
        md_api.registerFront(os.getenv("SOPT_REAL_MD_ADDRESS"))
        print(f"  Connecting to: {os.getenv('SOPT_REAL_MD_ADDRESS')}")
        md_api.init()

        # Wait for connection
        print("  Waiting for connection...")
        time.sleep(3)

        if md_api.connected:
            # Login
            req = {
                "BrokerID": os.getenv("SOPT_REAL_BROKER_ID"),
                "UserID": os.getenv("SOPT_REAL_USER_ID"),
                "Password": os.getenv("SOPT_REAL_PASSWORD"),
            }
            print(f"  Logging in as: {req['UserID']}")
            md_api.reqUserLogin(req, 1)
            time.sleep(3)

            if md_api.logged_in:
                print("✅ Direct SOPT API test successful")
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
    print("🚀 Real SOPT Account Test (Without pytest)")
    print("=" * 60)

    # Check environment
    print("\n📋 Environment Check:")
    user_id = os.getenv("SOPT_REAL_USER_ID")
    if not user_id:
        print("❌ SOPT_REAL_USER_ID not set in .env.test.local")
        print("\n📝 Please add the following to .env.test.local:")
        print("SOPT_REAL_USER_ID=your_user_id")
        print("SOPT_REAL_PASSWORD=your_password")
        print("SOPT_REAL_BROKER_ID=your_broker_id")
        print("SOPT_REAL_TD_ADDRESS=tcp://xxx.xxx.xxx.xxx:port")
        print("SOPT_REAL_MD_ADDRESS=tcp://xxx.xxx.xxx.xxx:port")
        return

    print(f"✅ SOPT Account: {user_id}")

    # Test import
    if not test_sopt_import():
        print("\n⚠️  Cannot proceed without vnpy_sopt module")
        return

    # Test direct API first (simpler, less dependencies)
    print("\n" + "=" * 40)
    print("Test 1: Direct SOPT API")
    print("=" * 40)
    await test_direct_sopt_api()

    # Test adapter
    print("\n" + "=" * 40)
    print("Test 2: SOPT Adapter")
    print("=" * 40)
    success, adapter, config = test_sopt_adapter()

    if success and adapter:
        # Test connection
        await test_sopt_connection(adapter)

    print("\n" + "=" * 60)
    print("✅ Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
