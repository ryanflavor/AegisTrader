"""
测试简化版市场服务
"""

import asyncio
import os
import random
from datetime import datetime

from aegis_sdk import Service
from aegis_sdk.infrastructure import NATSAdapter
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


async def main():
    """主函数"""
    # 加载环境变量
    load_dotenv()

    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    # 创建NATS适配器
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    adapter = NATSAdapter()
    await adapter.connect([nats_url])

    # 创建服务
    service = Service("vnpy-market-demo", adapter)

    # 订阅的符号
    subscribed_symbols = set()

    # 注册RPC处理器
    @service.rpc("subscribe")
    async def handle_subscribe(params: dict) -> dict:
        symbols = params.get("symbols", [])
        logger.info(f"Received subscribe request for symbols: {symbols}")
        subscribed_symbols.update(symbols)
        return {"success": symbols, "failed": [], "total_subscribed": len(subscribed_symbols)}

    @service.rpc("get_subscribed")
    async def handle_get_subscribed(params: dict) -> list[str]:
        return list(subscribed_symbols)

    # 启动服务
    await service.start()
    logger.info("Market service started")

    # 模拟行情推送
    base_prices = {"rb2501": 3800.0, "ag2501": 5500.0, "au2501": 450.0}

    try:
        while True:
            for symbol in list(subscribed_symbols):
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
                    await service.publish_event(
                        f"market.tick.{symbol_code}", tick_event.model_dump(mode="json")
                    )

                except Exception as e:
                    logger.error(f"Error simulating tick for {symbol}: {e}")

            await asyncio.sleep(1)  # 每秒推送一次

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await service.stop()
        await adapter.disconnect()


if __name__ == "__main__":
    import sys

    asyncio.run(main())
