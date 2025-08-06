#!/usr/bin/env python
"""
测试 OpenCTP 股票行情订阅
"""

import asyncio
import os
import sys

from aegis_sdk import Service
from aegis_sdk.domain.models import Event, RPCRequest
from aegis_sdk.infrastructure import NATSAdapter
from dotenv import load_dotenv
from loguru import logger


class StockTestClient(Service):
    """股票行情测试客户端"""

    def __init__(self, message_bus: NATSAdapter):
        super().__init__("stock-test-client", message_bus)
        self.tick_count = 0

    async def on_start(self):
        """启动时的操作"""
        logger.info("Stock test client started")

        # 订阅市场事件
        await self.subscribe_event("market", "tick.*", self.handle_market_tick)

    async def handle_market_tick(self, event: Event):
        """处理行情数据"""
        self.tick_count += 1
        tick_data = event.payload
        symbol = tick_data.get("symbol")
        price = tick_data.get("last_price", 0)
        volume = tick_data.get("volume", 0)
        time = tick_data.get("datetime")

        # 打印所有行情
        logger.info(f"[TICK #{self.tick_count}] {symbol} @ {price:.2f} Vol:{volume} Time:{time}")

    async def test_subscribe_stocks(self):
        """测试订阅股票行情"""
        logger.info("=== Testing Stock Subscription ===")

        # 订阅股票和期货合约
        contracts = [
            # 股票代码
            "000001.SZSE",  # 平安银行
            "10008799.SSE",  # 您提到的代码
            # 常见期货合约
            "rb2501.SHFE",  # 螺纹钢
            "ag2502.SHFE",  # 白银
            # ETF
            "510050.SSE",  # 50ETF
            "510300.SSE",  # 300ETF
            # 股指期货
            "IF2501.CFFEX",  # 沪深300股指期货
        ]

        request = RPCRequest(
            target="vnpy-market-demo", method="subscribe", params={"symbols": contracts}
        )

        try:
            result = await self.call_rpc(request)
            logger.info(f"Subscribe result: {result}")

            if result.get("success"):
                success_symbols = result.get("success", {}).get("symbols", [])
                logger.success(f"Successfully subscribed to {len(success_symbols)} contracts:")
                for symbol in success_symbols:
                    logger.info(f"  - {symbol}")

            failed = result.get("failed", [])
            if failed:
                logger.warning(f"Failed to subscribe: {failed}")

        except Exception as e:
            logger.error(f"Subscribe failed: {e}")

    async def run_tests(self):
        """运行测试"""
        logger.info("Starting stock subscription tests in 3 seconds...")
        await asyncio.sleep(3)

        # 订阅股票行情
        await self.test_subscribe_stocks()

        # 等待行情
        logger.info("\nWaiting for market data...")
        await asyncio.sleep(10)

        # 显示统计
        logger.info("\n=== Statistics ===")
        logger.info(f"Total ticks received: {self.tick_count}")

        if self.tick_count > 0:
            logger.success("✓ Successfully receiving market data!")
        else:
            logger.warning("⚠ No market data received. The market might be closed.")

        logger.info("\nContinuing to receive events... Press Ctrl+C to stop")


async def main():
    """主函数"""
    # 加载环境变量
    load_dotenv(".env.openctp")

    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    logger.info("=== OpenCTP Stock Market Test ===")
    logger.info("Testing symbols: 000001, 10008799")

    # 创建NATS适配器
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    adapter = NATSAdapter()
    await adapter.connect([nats_url])
    logger.info(f"Connected to NATS at {nats_url}")

    # 创建客户端
    client = StockTestClient(adapter)

    # 启动客户端
    await client.start()

    # 运行测试
    asyncio.create_task(client.run_tests())

    # 保持运行
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await client.stop()
        await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
