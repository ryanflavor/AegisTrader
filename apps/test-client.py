"""
测试客户端 - 演示如何通过SDK与vnpy服务通信
"""

import asyncio
import os
import sys
from datetime import datetime

from aegis_sdk import Service
from aegis_sdk.domain.models import Event, RPCRequest
from aegis_sdk.infrastructure import NATSAdapter
from loguru import logger


class TestClient(Service):
    """测试客户端"""

    def __init__(self, message_bus: NATSAdapter):
        super().__init__("test-client", message_bus)

    async def on_start(self):
        """启动时的操作"""
        logger.info("Test client started")

        # 订阅市场事件
        await self.subscribe_event("market", "tick.*", self.handle_market_tick)
        await self.subscribe_event("trading", "order.*", self.handle_order_update)
        await self.subscribe_event("trading", "trade.*", self.handle_trade_update)

    async def handle_market_tick(self, event: Event):
        """处理行情数据"""
        event_data = event.payload
        symbol = event_data.get("symbol")
        price = event_data.get("last_price")
        time = event_data.get("datetime")
        logger.info(f"[TICK] {symbol} @ {price} at {time}")

    async def handle_order_update(self, event: Event):
        """处理订单更新"""
        event_data = event.payload
        order_id = event_data.get("order_id")
        status = event_data.get("status")
        logger.info(f"[ORDER] {order_id} - Status: {status}")

    async def handle_trade_update(self, event: Event):
        """处理成交更新"""
        event_data = event.payload
        trade_id = event_data.get("trade_id")
        price = event_data.get("price")
        volume = event_data.get("volume")
        logger.info(f"[TRADE] {trade_id} - {volume} @ {price}")

    async def test_market_subscribe(self):
        """测试订阅行情"""
        logger.info("=== Testing Market Subscribe ===")

        # 订阅一些合约
        symbols = ["rb2501.SHFE", "ag2501.SHFE", "au2501.SHFE"]

        request = RPCRequest(
            target="vnpy-market-demo", method="subscribe", params={"symbols": symbols}
        )
        result = await self.call_rpc(request)

        logger.info(f"Subscribe result: {result}")

    async def test_get_account(self):
        """测试获取账户信息"""
        logger.info("=== Testing Get Account ===")

        request = RPCRequest(target="vnpy-trading-demo", method="get_account", params={})
        result = await self.call_rpc(request)

        logger.info(f"Account info: {result}")

    async def test_send_order(self):
        """测试下单"""
        logger.info("=== Testing Send Order ===")

        # 构造下单命令
        order_command = {
            "symbol": "rb2501",
            "exchange": "SHFE",
            "direction": "LONG",
            "offset": "OPEN",
            "order_type": "LIMIT",
            "price": 3800.0,
            "volume": 1,
            "reference": f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        }

        request = RPCRequest(target="vnpy-trading-demo", method="send_order", params=order_command)
        result = await self.call_rpc(request)

        logger.info(f"Send order result: {result}")
        return result

    async def test_cancel_order(self, order_id: str):
        """测试撤单"""
        logger.info("=== Testing Cancel Order ===")

        request = RPCRequest(
            target="vnpy-trading-demo", method="cancel_order", params={"order_id": order_id}
        )
        result = await self.call_rpc(request)

        logger.info(f"Cancel order result: {result}")

    async def test_get_positions(self):
        """测试获取持仓"""
        logger.info("=== Testing Get Positions ===")

        request = RPCRequest(target="vnpy-trading-demo", method="get_positions", params={})
        result = await self.call_rpc(request)

        logger.info(f"Positions: {result}")

    async def run_tests(self):
        """运行所有测试"""
        logger.info("Starting tests in 10 seconds to let services fully initialize...")
        await asyncio.sleep(10)

        # 1. 测试订阅行情
        await self.test_market_subscribe()
        await asyncio.sleep(2)

        # 2. 测试获取账户
        await self.test_get_account()
        await asyncio.sleep(1)

        # 3. 测试获取持仓
        await self.test_get_positions()
        await asyncio.sleep(1)

        # 4. 测试下单
        order_result = await self.test_send_order()
        await asyncio.sleep(2)

        # 5. 测试撤单
        if order_result and order_result.get("success"):
            order_id = order_result.get("order_id")
            if order_id:
                await self.test_cancel_order(order_id)

        # 继续接收事件
        logger.info("Tests completed. Listening for events...")


async def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    # 创建NATS适配器并连接
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    adapter = NATSAdapter()
    await adapter.connect([nats_url])
    logger.info(f"Connected to NATS at {nats_url}")

    # 创建客户端
    client = TestClient(adapter)

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
