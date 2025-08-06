#!/usr/bin/env python
"""
测试 OpenCTP 连接
"""

import asyncio
import os
import sys
from datetime import datetime

from aegis_sdk import Service
from aegis_sdk.domain.models import Event, RPCRequest
from aegis_sdk.infrastructure import NATSAdapter
from dotenv import load_dotenv
from loguru import logger


class OpenCTPTestClient(Service):
    """OpenCTP 测试客户端"""

    def __init__(self, message_bus: NATSAdapter):
        super().__init__("openctp-test-client", message_bus)
        self.tick_count = 0
        self.order_count = 0

    async def on_start(self):
        """启动时的操作"""
        logger.info("OpenCTP test client started")

        # 订阅市场事件
        await self.subscribe_event("market", "tick.*", self.handle_market_tick)
        await self.subscribe_event("trading", "order.*", self.handle_order_update)
        await self.subscribe_event("trading", "trade.*", self.handle_trade_update)

    async def handle_market_tick(self, event: Event):
        """处理行情数据"""
        self.tick_count += 1
        tick_data = event.payload
        symbol = tick_data.get("symbol")
        price = tick_data.get("last_price")
        time = tick_data.get("datetime")

        # 每10个tick打印一次
        if self.tick_count % 10 == 0:
            logger.info(f"[TICK #{self.tick_count}] {symbol} @ {price} at {time}")

    async def handle_order_update(self, event: Event):
        """处理订单更新"""
        order_data = event.payload
        order_id = order_data.get("order_id")
        status = order_data.get("status")
        logger.info(f"[ORDER] {order_id} - Status: {status}")

    async def handle_trade_update(self, event: Event):
        """处理成交更新"""
        trade_data = event.payload
        trade_id = trade_data.get("trade_id")
        price = trade_data.get("price")
        volume = trade_data.get("volume")
        logger.info(f"[TRADE] {trade_id} - {volume} @ {price}")

    async def test_subscribe_contracts(self):
        """测试订阅合约行情"""
        logger.info("=== Testing Contract Subscription ===")

        # 订阅主力合约
        contracts = [
            "rb2501.SHFE",  # 螺纹钢
            "ag2502.SHFE",  # 白银
            "au2502.SHFE",  # 黄金
            "cu2501.SHFE",  # 铜
            "IF2501.CFFEX",  # 沪深300股指期货
            "IC2501.CFFEX",  # 中证500股指期货
            "IH2501.CFFEX",  # 上证50股指期货
        ]

        request = RPCRequest(
            target="vnpy-market-demo", method="subscribe", params={"symbols": contracts}
        )

        try:
            result = await self.call_rpc(request)
            logger.info(f"Subscribe result: {result}")

            if result.success:
                logger.success(f"Successfully subscribed to {len(contracts)} contracts")
            else:
                logger.error("Failed to subscribe to contracts")

        except Exception as e:
            logger.error(f"Subscribe failed: {e}")

    async def test_get_account(self):
        """测试获取账户信息"""
        logger.info("=== Testing Get Account Info ===")

        request = RPCRequest(target="vnpy-trading-demo", method="get_account", params={})

        try:
            result = await self.call_rpc(request)

            if result.success:
                account = result.result.get("account", {})
                logger.info(f"Account Balance: {account.get('balance', 0)}")
                logger.info(f"Available: {account.get('available', 0)}")
                logger.info(f"Frozen: {account.get('frozen', 0)}")
            else:
                logger.error("Failed to get account info")

        except Exception as e:
            logger.error(f"Get account failed: {e}")

    async def test_send_order(self):
        """测试下单（小额测试单）"""
        logger.info("=== Testing Send Order ===")

        # 构造测试订单 - 远离市价的限价单
        order_command = {
            "symbol": "rb2501",
            "exchange": "SHFE",
            "direction": "LONG",
            "offset": "OPEN",
            "order_type": "LIMIT",
            "price": 3000.0,  # 远低于市价的价格，避免成交
            "volume": 1,
            "reference": f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        }

        request = RPCRequest(target="vnpy-trading-demo", method="send_order", params=order_command)

        try:
            result = await self.call_rpc(request)

            if result.success:
                order_id = result.result.get("order_id")
                logger.success(f"Order sent successfully: {order_id}")
                return order_id
            else:
                logger.error(f"Send order failed: {result.error}")

        except Exception as e:
            logger.error(f"Send order error: {e}")

        return None

    async def run_tests(self):
        """运行所有测试"""
        logger.info("Starting OpenCTP connection tests in 5 seconds...")
        await asyncio.sleep(5)

        # 1. 测试账户信息
        await self.test_get_account()
        await asyncio.sleep(2)

        # 2. 测试订阅行情
        await self.test_subscribe_contracts()
        await asyncio.sleep(5)

        # 3. 检查是否收到行情
        if self.tick_count > 0:
            logger.success(f"✓ Received {self.tick_count} market ticks")
        else:
            logger.warning("⚠ No market ticks received yet")

        # 4. 测试下单（可选）
        if os.getenv("TEST_TRADING", "false").lower() == "true":
            order_id = await self.test_send_order()
            if order_id:
                await asyncio.sleep(3)
                # 这里可以添加撤单测试

        # 继续接收事件
        logger.info("\n=== Test Summary ===")
        logger.info(f"Market ticks received: {self.tick_count}")
        logger.info(f"Orders processed: {self.order_count}")
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

    logger.info("=== OpenCTP Connection Test ===")
    logger.info(f"CTP User: {os.getenv('CTP_USER_ID')}")
    logger.info(f"MD Address: {os.getenv('CTP_MD_ADDRESS')}")
    logger.info(f"TD Address: {os.getenv('CTP_TD_ADDRESS')}")

    # 创建NATS适配器
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    adapter = NATSAdapter()
    await adapter.connect([nats_url])
    logger.info(f"Connected to NATS at {nats_url}")

    # 创建客户端
    client = OpenCTPTestClient(adapter)

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
