"""
VNPy Market Data Demo Service - 简化版本（不使用MainEngine）
使用OpenCTP 7x24环境获取行情数据，通过AegisSDK分发
"""

import asyncio
import os
import signal
import sys
from datetime import datetime
from typing import Any

from aegis_sdk import Service
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel


class MarketTickEvent(BaseModel):
    """SDK格式的行情事件"""

    symbol: str
    exchange: str
    datetime: datetime
    last_price: float
    volume: int
    bid_price_1: float
    bid_volume_1: int
    ask_price_1: float
    ask_volume_1: int
    open_interest: float


class SimpleMarketService(Service):
    """简化的行情服务 - 模拟vnpy行情"""

    def __init__(self):
        super().__init__("vnpy-market-demo")
        self.subscribed_symbols = set()
        self.running = False

    async def setup(self):
        """服务启动"""
        logger.info("Starting Simple Market Service...")

        # 注册RPC方法
        self.register_rpc("subscribe", self.handle_subscribe)
        self.register_rpc("unsubscribe", self.handle_unsubscribe)
        self.register_rpc("get_subscribed", self.handle_get_subscribed)

        # 启动模拟行情
        self.running = True
        asyncio.create_task(self._simulate_market_data())

        logger.info("Simple Market Service started successfully")

    async def _simulate_market_data(self):
        """模拟行情数据推送"""
        import random

        base_prices = {"rb2501": 3800.0, "ag2501": 5500.0, "au2501": 450.0}

        while self.running:
            for symbol in list(self.subscribed_symbols):
                try:
                    # 解析symbol
                    parts = symbol.split(".")
                    if len(parts) != 2:
                        continue

                    symbol_code = parts[0]
                    exchange = parts[1]

                    # 获取基准价格
                    base_price = base_prices.get(symbol_code, 1000.0)

                    # 生成随机行情
                    price_change = random.uniform(-10, 10)
                    last_price = base_price + price_change

                    tick_event = MarketTickEvent(
                        symbol=symbol_code,
                        exchange=exchange,
                        datetime=datetime.now(),
                        last_price=last_price,
                        volume=random.randint(100, 1000),
                        bid_price_1=last_price - 1,
                        bid_volume_1=random.randint(10, 100),
                        ask_price_1=last_price + 1,
                        ask_volume_1=random.randint(10, 100),
                        open_interest=random.randint(10000, 50000),
                    )

                    # 发布行情事件
                    await self.publish_event(
                        f"market.tick.{symbol_code}", tick_event.model_dump(mode="json")
                    )

                except Exception as e:
                    logger.error(f"Error simulating tick for {symbol}: {e}")

            await asyncio.sleep(1)  # 每秒推送一次

    async def handle_subscribe(self, symbols: list[str]) -> dict[str, Any]:
        """处理订阅请求"""
        logger.info(f"Received subscribe request for symbols: {symbols}")

        success = []
        failed = []

        for symbol in symbols:
            try:
                # 简单验证格式
                parts = symbol.split(".")
                if len(parts) != 2:
                    failed.append(f"{symbol}: Invalid format")
                    continue

                self.subscribed_symbols.add(symbol)
                success.append(symbol)

            except Exception as e:
                failed.append(f"{symbol}: {str(e)}")

        return {
            "success": success,
            "failed": failed,
            "total_subscribed": len(self.subscribed_symbols),
        }

    async def handle_unsubscribe(self, symbols: list[str]) -> dict[str, Any]:
        """处理取消订阅请求"""
        logger.info(f"Received unsubscribe request for symbols: {symbols}")

        for symbol in symbols:
            self.subscribed_symbols.discard(symbol)

        return {"unsubscribed": symbols, "total_subscribed": len(self.subscribed_symbols)}

    async def handle_get_subscribed(self) -> list[str]:
        """获取当前订阅的合约列表"""
        return list(self.subscribed_symbols)

    async def teardown(self):
        """服务停止时清理"""
        logger.info("Stopping Simple Market Service...")
        self.running = False
        logger.info("Simple Market Service stopped")


def signal_handler(signum, frame):
    """处理退出信号"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


async def main():
    """主函数"""
    # 加载环境变量
    load_dotenv()

    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=os.getenv("LOG_LEVEL", "INFO"),
    )

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 创建并启动服务
    service = SimpleMarketService()
    await service.start()

    # 保持运行
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
