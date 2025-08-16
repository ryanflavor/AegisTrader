#!/usr/bin/env python
"""
导出所有CTP合约信息到JSON文件（基于验证过的test_real_ctp.py）
Export all CTP instruments to JSON file (based on verified test_real_ctp.py)
"""

import json
import locale
import os
import sys
import time
from datetime import datetime
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
            print("⚠️  zh_CN.gb18030 locale not available.")


def export_ctp_instruments():
    """导出CTP合约信息"""
    print("\n🔧 Exporting CTP Instruments...")

    try:
        # Add vnpy_ctp to path
        vnpy_ctp_path = project_root / "vnpy_ctp"
        sys.path.insert(0, str(vnpy_ctp_path))

        from vnpy_ctp.api import TdApi

        class InstrumentCollector(TdApi):
            """Collect all instruments from CTP"""

            def __init__(self):
                super().__init__()
                self.connected = False
                self.logged_in = False
                self.authenticated = False
                self.settlement_confirmed = False
                self.instruments = []
                self.error = None

            def onFrontConnected(self):
                print("  ✅ TD Front Connected")
                self.connected = True

            def onRspAuthenticate(self, data, error, reqid, last):
                if error and error["ErrorID"] != 0:
                    print(f"  ❌ Auth Error: {error}")
                    self.error = error
                else:
                    print("  ✅ Authentication Success")
                    self.authenticated = True

            def onRspUserLogin(self, data, error, reqid, last):
                if error and error["ErrorID"] != 0:
                    print(f"  ❌ TD Login Error: {error}")
                    self.error = error
                else:
                    print("  ✅ TD Login Success")
                    self.logged_in = True
                    if data:
                        print(f"    Trading Day: {data.get('TradingDay')}")
                        print(f"    Front ID: {data.get('FrontID')}")
                        print(f"    Session ID: {data.get('SessionID')}")

            def onRspQryInstrument(self, data, error, reqid, last):
                """合约查询回调"""
                if error and error["ErrorID"] != 0:
                    print(f"  ❌ Query Error: {error}")
                    return

                if data:
                    # Convert data to dictionary and clean up
                    inst_dict = {}
                    for key, value in data.items():
                        # Convert bytes to string if needed
                        if isinstance(value, bytes):
                            try:
                                inst_dict[key] = value.decode("gb18030").strip()
                            except:
                                inst_dict[key] = str(value)
                        else:
                            inst_dict[key] = value
                    self.instruments.append(inst_dict)

                if last:
                    print(f"  ✅ Received {len(self.instruments)} instruments")

            def onRspSettlementInfoConfirm(self, data, error, reqid, last):
                """结算确认回调"""
                if error and error["ErrorID"] != 0:
                    print(f"  ❌ Settlement Error: {error}")
                else:
                    print("  ✅ Settlement Confirmed")
                    self.settlement_confirmed = True

        # Create collector
        collector = InstrumentCollector()

        # Clean temp directory
        import shutil

        temp_dir = "/tmp/export_ctp_instruments_real"
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

        # Initialize
        collector.createFtdcTraderApi(temp_dir)

        # Use primary TD address first
        td_address = os.getenv("CTP_REAL_TD_ADDRESS")
        collector.registerFront(td_address)
        print(f"  Connecting to: {td_address}")
        collector.init()

        # Wait for connection
        print("  Waiting for connection...")
        time.sleep(3)

        if collector.connected:
            # CTP authentication
            auth_req = {
                "BrokerID": os.getenv("CTP_REAL_BROKER_ID"),
                "UserID": os.getenv("CTP_REAL_USER_ID"),
                "AppID": os.getenv("CTP_REAL_APP_ID", "client_vntech_2.0"),
                "AuthCode": os.getenv("CTP_REAL_AUTH_CODE", "52TMMTN41F3KFR83"),
            }

            print(f"  Authenticating as: {auth_req['UserID']}")
            collector.reqAuthenticate(auth_req, 1)
            time.sleep(2)

            if collector.authenticated:
                # Login
                login_req = {
                    "BrokerID": os.getenv("CTP_REAL_BROKER_ID"),
                    "UserID": os.getenv("CTP_REAL_USER_ID"),
                    "Password": os.getenv("CTP_REAL_PASSWORD"),
                }

                print("  Logging in...")
                collector.reqUserLogin(login_req, 2)
                time.sleep(3)

                if collector.logged_in:
                    # Confirm settlement
                    settlement_req = {
                        "BrokerID": os.getenv("CTP_REAL_BROKER_ID"),
                        "InvestorID": os.getenv("CTP_REAL_USER_ID"),
                    }
                    print("  Confirming settlement...")
                    collector.reqSettlementInfoConfirm(settlement_req, 3)
                    time.sleep(2)

                    # Query all instruments
                    print("\n  📊 Querying All Instruments...")
                    instrument_req = {}  # Empty dict queries all
                    collector.reqQryInstrument(instrument_req, 4)

                    # Wait longer for all instruments
                    print("  Waiting for instruments (this may take a while)...")
                    time.sleep(30)

                    if collector.instruments:
                        # Save to JSON file
                        output_dir = project_root / "data"
                        output_dir.mkdir(exist_ok=True)

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_file = output_dir / f"ctp_instruments_{timestamp}.json"

                        print(
                            f"\n  💾 Saving {len(collector.instruments)} instruments to {output_file}"
                        )

                        # Prepare data with metadata
                        export_data = {
                            "metadata": {
                                "source": "CTP",
                                "broker_id": os.getenv("CTP_REAL_BROKER_ID"),
                                "export_time": datetime.now().isoformat(),
                                "total_count": len(collector.instruments),
                                "trading_day": (
                                    collector.instruments[0].get("TradingDay")
                                    if collector.instruments
                                    else None
                                ),
                            },
                            "instruments": collector.instruments,
                        }

                        # Write to file
                        with open(output_file, "w", encoding="utf-8") as f:
                            json.dump(export_data, f, ensure_ascii=False, indent=2)

                        print(f"  ✅ Exported to {output_file}")

                        # Generate summary
                        print("\n  📈 Export Summary:")

                        # Count by exchange
                        exchanges = {}
                        for inst in collector.instruments:
                            exchange = inst.get("ExchangeID", "UNKNOWN")
                            if exchange not in exchanges:
                                exchanges[exchange] = 0
                            exchanges[exchange] += 1

                        print("  By Exchange:")
                        for exchange, count in sorted(exchanges.items()):
                            print(f"    {exchange}: {count} instruments")

                        # Count by product type
                        products = {}
                        for inst in collector.instruments:
                            product = inst.get("ProductID", "UNKNOWN")
                            if product not in products:
                                products[product] = 0
                            products[product] += 1

                        print("\n  Top Product Types (by count):")
                        for product, count in sorted(
                            products.items(), key=lambda x: x[1], reverse=True
                        )[:15]:
                            print(f"    {product}: {count} instruments")

                        # Count futures by underlying
                        underlyings = {}
                        for inst in collector.instruments:
                            # For futures, extract base product from InstrumentID
                            inst_id = inst.get("InstrumentID", "")
                            # Extract product code (letters before numbers)
                            import re

                            match = re.match(r"^([A-Za-z]+)", inst_id)
                            if match:
                                product_code = match.group(1)
                                if product_code not in underlyings:
                                    underlyings[product_code] = []
                                underlyings[product_code].append(inst_id)

                        print("\n  Top Products (by contract count):")
                        for product, contracts in sorted(
                            underlyings.items(), key=lambda x: len(x[1]), reverse=True
                        )[:15]:
                            print(f"    {product}: {len(contracts)} contracts")

                        # Sample first 5 instruments
                        print("\n  Sample Instruments (first 5):")
                        for i, inst in enumerate(collector.instruments[:5]):
                            print(f"\n  [{i + 1}] Instrument Details:")
                            print(f"    InstrumentID: {inst.get('InstrumentID', 'N/A')}")
                            print(f"    ExchangeID: {inst.get('ExchangeID', 'N/A')}")
                            print(f"    InstrumentName: {inst.get('InstrumentName', 'N/A')}")
                            print(f"    ProductID: {inst.get('ProductID', 'N/A')}")
                            print(f"    ProductClass: {inst.get('ProductClass', 'N/A')}")
                            print(f"    VolumeMultiple: {inst.get('VolumeMultiple', 'N/A')}")
                            print(f"    PriceTick: {inst.get('PriceTick', 'N/A')}")
                            print(f"    ExpireDate: {inst.get('ExpireDate', 'N/A')}")

                        # Create a simplified CSV file for easy viewing
                        csv_file = output_dir / f"ctp_instruments_{timestamp}.csv"
                        print(f"\n  📄 Creating simplified CSV: {csv_file}")

                        import csv

                        with open(csv_file, "w", newline="", encoding="utf-8") as f:
                            fieldnames = [
                                "InstrumentID",
                                "InstrumentName",
                                "ExchangeID",
                                "ProductID",
                                "ProductClass",
                                "DeliveryYear",
                                "DeliveryMonth",
                                "VolumeMultiple",
                                "PriceTick",
                                "CreateDate",
                                "ExpireDate",
                                "MaxMarketOrderVolume",
                                "MinMarketOrderVolume",
                                "MaxLimitOrderVolume",
                                "MinLimitOrderVolume",
                                "IsTrading",
                                "PositionType",
                                "PositionDateType",
                            ]
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()

                            for inst in collector.instruments:
                                row = {field: inst.get(field, "") for field in fieldnames}
                                writer.writerow(row)

                        print(f"  ✅ CSV exported to {csv_file}")

                        return True
                    else:
                        print("  ❌ No instruments received")
                        print("  ℹ️  This might be due to market hours or API restrictions")
                        return False
                else:
                    print(f"  ❌ Login failed: {collector.error}")
                    return False
            else:
                print(f"  ❌ Authentication failed: {collector.error}")
                return False
        else:
            print("  ❌ Connection failed")
            print(f"  ℹ️  Check if the TD address is correct: {td_address}")
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 CTP Instruments Export Tool (Real Account)")
    print("=" * 60)

    # Check environment
    print("\n📋 Environment Check:")
    user_id = os.getenv("CTP_REAL_USER_ID")
    if not user_id:
        print("❌ CTP_REAL_USER_ID not set in .env.test.local")
        return

    print(f"✅ CTP Account: {user_id}")
    print(f"✅ Broker ID: {os.getenv('CTP_REAL_BROKER_ID')}")
    print(f"✅ TD Address: {os.getenv('CTP_REAL_TD_ADDRESS')}")

    # Export instruments
    success = export_ctp_instruments()

    print("\n" + "=" * 60)
    if success:
        print("✅ Export Complete")
    else:
        print("❌ Export Failed")
    print("=" * 60)


if __name__ == "__main__":
    main()
