#!/usr/bin/env python
"""测试vnpy安装是否成功"""

import sys

try:
    # 测试导入vnpy核心模块
    print("Testing vnpy imports...")

    from vnpy.event import EventEngine

    print("✓ EventEngine imported successfully")

    from vnpy.trader.engine import MainEngine

    print("✓ MainEngine imported successfully")

    from vnpy.trader.object import OrderData, TickData, TradeData

    print("✓ Trading objects imported successfully")

    from vnpy_ctp import CtpGateway

    print("✓ CtpGateway imported successfully")

    # 测试创建基本对象
    print("\nTesting object creation...")

    event_engine = EventEngine()
    print("✓ EventEngine created successfully")

    main_engine = MainEngine(event_engine)
    print("✓ MainEngine created successfully")

    # 测试TA-Lib
    print("\nTesting TA-Lib...")
    import numpy as np
    import talib

    # 创建测试数据
    close_prices = np.random.random(100)
    sma = talib.SMA(close_prices, timeperiod=10)
    print(f"✓ TA-Lib working - SMA calculated: {sma[-1]:.4f}")

    print("\n🎉 All tests passed! vnpy is properly installed.")

except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
