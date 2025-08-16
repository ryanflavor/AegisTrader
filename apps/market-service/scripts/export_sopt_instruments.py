#!/usr/bin/env python
"""
导出所有SOPT合约信息到JSON文件
Export all SOPT instruments to JSON file
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

# Set locale for SOPT
if os.name != "nt":
    try:
        os.environ["LC_ALL"] = "zh_CN.gb18030"
        os.environ["LANG"] = "zh_CN.gb18030"
        locale.setlocale(locale.LC_ALL, "zh_CN.gb18030")
        print("✅ Locale set to zh_CN.gb18030")
    except locale.Error:
        print("⚠️  zh_CN.gb18030 locale not available")


def export_sopt_instruments():
    """导出SOPT合约信息"""
    print("\n🔧 Exporting SOPT Instruments...")

    try:
        # Move local vnpy_sopt to avoid conflict
        local_vnpy = project_root / "vnpy_sopt"
        local_vnpy_bak = project_root / "vnpy_sopt_bak"
        if local_vnpy.exists():
            os.rename(local_vnpy, local_vnpy_bak)

        # Import from installed package
        import vnpy_sopt

        print(f"  Using vnpy_sopt from: {vnpy_sopt.__file__}")

        from vnpy_sopt.api import TdApi

        class InstrumentCollector(TdApi):
            """Collect all instruments from SOPT"""

            def __init__(self):
                super().__init__()
                self.connected = False
                self.logged_in = False
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

            def onRspUserLogin(self, data, error, reqid, last):
                if error and error["ErrorID"] != 0:
                    print(f"  ❌ TD Login Error: {error}")
                    self.error = error
                else:
                    print("  ✅ TD Login Success")
                    self.logged_in = True
                    if data:
                        print(f"    Trading Day: {data.get('TradingDay')}")

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

        # Create collector
        collector = InstrumentCollector()

        # Clean temp directory
        import shutil

        temp_dir = "/tmp/export_sopt_instruments"
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

        # Initialize
        collector.createFtdcTraderApi(temp_dir)
        collector.registerFront(os.getenv("SOPT_REAL_TD_ADDRESS"))
        print(f"  Connecting to: {os.getenv('SOPT_REAL_TD_ADDRESS')}")
        collector.init()

        # Wait for connection
        print("  Waiting for connection...")
        time.sleep(3)

        if collector.connected:
            # Authenticate
            auth_req = {
                "BrokerID": os.getenv("SOPT_REAL_BROKER_ID"),
                "UserID": os.getenv("SOPT_REAL_USER_ID"),
                "AppID": os.getenv("SOPT_REAL_APP_ID", "client_vntech_2.0"),
                "AuthCode": os.getenv("SOPT_REAL_AUTH_CODE", "52TMMTN41F3KFR83"),
            }
            print("  Authenticating...")
            collector.reqAuthenticate(auth_req, 1)
            time.sleep(2)

            # Login
            login_req = {
                "BrokerID": os.getenv("SOPT_REAL_BROKER_ID"),
                "UserID": os.getenv("SOPT_REAL_USER_ID"),
                "Password": os.getenv("SOPT_REAL_PASSWORD"),
            }
            print("  Logging in...")
            collector.reqUserLogin(login_req, 2)
            time.sleep(3)

            if collector.logged_in:
                # Confirm settlement
                settlement_req = {
                    "BrokerID": os.getenv("SOPT_REAL_BROKER_ID"),
                    "InvestorID": os.getenv("SOPT_REAL_USER_ID"),
                }
                print("  Confirming settlement...")
                collector.reqSettlementInfoConfirm(settlement_req, 3)
                time.sleep(2)

                # Query all instruments
                print("\n  📊 Querying All Instruments...")
                instrument_req = {}  # Empty dict queries all
                collector.reqQryInstrument(instrument_req, 4)
                time.sleep(15)  # Wait longer for all instruments

                if collector.instruments:
                    # Save to JSON file
                    output_dir = project_root / "data"
                    output_dir.mkdir(exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_file = output_dir / f"sopt_instruments_{timestamp}.json"

                    print(
                        f"\n  💾 Saving {len(collector.instruments)} instruments to {output_file}"
                    )

                    # Prepare data with metadata
                    export_data = {
                        "metadata": {
                            "source": "SOPT",
                            "broker_id": os.getenv("SOPT_REAL_BROKER_ID"),
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
                    for exchange, count in exchanges.items():
                        print(f"    {exchange}: {count} instruments")

                    # Count by product type
                    products = {}
                    for inst in collector.instruments:
                        product = inst.get("ProductID", "UNKNOWN")
                        if product not in products:
                            products[product] = 0
                        products[product] += 1

                    print("\n  By Product Type:")
                    for product, count in sorted(
                        products.items(), key=lambda x: x[1], reverse=True
                    )[:10]:
                        print(f"    {product}: {count} instruments")

                    # Count options by underlying
                    underlyings = {}
                    for inst in collector.instruments:
                        underlying = inst.get("UnderlyingInstrID")
                        if underlying:
                            if underlying not in underlyings:
                                underlyings[underlying] = []
                            underlyings[underlying].append(inst.get("InstrumentID"))

                    print("\n  Top Underlying Assets (by option count):")
                    for underlying, options in sorted(
                        underlyings.items(), key=lambda x: len(x[1]), reverse=True
                    )[:10]:
                        print(f"    {underlying}: {len(options)} options")

                    # Create a simplified CSV file for easy viewing
                    csv_file = output_dir / f"sopt_instruments_{timestamp}.csv"
                    print(f"\n  📄 Creating simplified CSV: {csv_file}")

                    import csv

                    with open(csv_file, "w", newline="", encoding="utf-8") as f:
                        fieldnames = [
                            "InstrumentID",
                            "InstrumentName",
                            "ExchangeID",
                            "ProductID",
                            "UnderlyingInstrID",
                            "OptionsType",
                            "StrikePrice",
                            "ExpireDate",
                            "VolumeMultiple",
                            "PriceTick",
                            "MaxMarketOrderVolume",
                            "MinMarketOrderVolume",
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
                    return False
            else:
                print("  ❌ Login failed")
                return False
        else:
            print("  ❌ Connection failed")
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Restore local vnpy_sopt folder
        if local_vnpy_bak.exists():
            os.rename(local_vnpy_bak, local_vnpy)


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 SOPT Instruments Export Tool")
    print("=" * 60)

    # Export instruments
    success = export_sopt_instruments()

    print("\n" + "=" * 60)
    if success:
        print("✅ Export Complete")
    else:
        print("❌ Export Failed")
    print("=" * 60)


if __name__ == "__main__":
    main()
