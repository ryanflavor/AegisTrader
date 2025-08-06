"""
简化版交易服务 - 不依赖vnpy的测试版本
"""

import asyncio
import os
import sys
from datetime import datetime

from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.domain.models import Event
from aegis_sdk.infrastructure import NATSAdapter
from loguru import logger
from pydantic import BaseModel


class OrderCommand(BaseModel):
    """下单命令"""

    symbol: str
    exchange: str
    direction: str  # LONG/SHORT
    offset: str  # OPEN/CLOSE
    order_type: str  # LIMIT/MARKET
    price: float
    volume: int
    reference: str  # 自定义引用


class SimpleTradingService(SingleActiveService):
    """简化版交易服务"""

    def __init__(self, service_id: str, message_bus: NATSAdapter):
        super().__init__(service_id, message_bus)
        self._orders = {}
        self._positions = {}
        self._account = {
            "balance": 100000.0,
            "available": 100000.0,
            "frozen": 0.0,
            "currency": "CNY",
        }

    async def on_start(self):
        """服务启动时的设置"""
        await super().on_start()

        # 注册RPC方法
        await self.register_rpc_method("send_order", self.handle_send_order)
        await self.register_rpc_method("cancel_order", self.handle_cancel_order)
        await self.register_rpc_method("get_positions", self.handle_get_positions)
        await self.register_rpc_method("get_account", self.handle_get_account)

        # 订阅市场事件
        await self.subscribe_event("market", "tick.*", self.handle_market_tick)

        logger.info("Trading service setup completed")

    async def handle_send_order(self, params: dict) -> dict:
        """处理下单请求"""
        try:
            order_cmd = OrderCommand(**params)
            order_id = f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._orders)}"

            # 创建订单
            order = {
                "order_id": order_id,
                "symbol": order_cmd.symbol,
                "exchange": order_cmd.exchange,
                "direction": order_cmd.direction,
                "offset": order_cmd.offset,
                "order_type": order_cmd.order_type,
                "price": order_cmd.price,
                "volume": order_cmd.volume,
                "traded_volume": 0,
                "status": "SUBMITTED",
                "reference": order_cmd.reference,
                "create_time": datetime.now().isoformat(),
            }

            self._orders[order_id] = order

            # 发布订单事件
            event = self.create_event("trading", "order.submitted", order)
            await self.publish_event(event)

            logger.info(f"Order submitted: {order_id}")

            # 模拟成交
            await asyncio.sleep(0.5)
            await self._simulate_trade(order_id)

            return {"success": True, "order_id": order_id}

        except Exception as e:
            logger.error(f"Send order failed: {e}")
            return {"success": False, "error": str(e)}

    async def handle_cancel_order(self, params: dict) -> dict:
        """处理撤单请求"""
        order_id = params.get("order_id")

        if order_id not in self._orders:
            return {"success": False, "error": "Order not found"}

        order = self._orders[order_id]

        if order["status"] not in ["SUBMITTED", "PARTIAL_FILLED"]:
            return {"success": False, "error": f"Cannot cancel order in status {order['status']}"}

        order["status"] = "CANCELLED"

        # 发布撤单事件
        event = self.create_event("trading", "order.cancelled", order)
        await self.publish_event(event)

        logger.info(f"Order cancelled: {order_id}")
        return {"success": True}

    async def handle_get_positions(self, params: dict) -> dict:
        """获取持仓信息"""
        positions = list(self._positions.values())
        return {"success": True, "positions": positions}

    async def handle_get_account(self, params: dict) -> dict:
        """获取账户信息"""
        return {"success": True, "account": self._account}

    async def handle_market_tick(self, event: Event):
        """处理行情事件"""
        tick_data = event.payload
        logger.debug(f"Received tick: {tick_data.get('symbol')} @ {tick_data.get('last_price')}")

    async def _simulate_trade(self, order_id: str):
        """模拟成交"""
        if order_id not in self._orders:
            return

        order = self._orders[order_id]

        if order["status"] != "SUBMITTED":
            return

        # 模拟全部成交
        order["status"] = "ALL_TRADED"
        order["traded_volume"] = order["volume"]

        # 更新持仓
        position_key = f"{order['symbol']}.{order['direction']}"

        if position_key not in self._positions:
            self._positions[position_key] = {
                "symbol": order["symbol"],
                "exchange": order["exchange"],
                "direction": order["direction"],
                "volume": 0,
                "frozen": 0,
                "price": 0,
                "pnl": 0,
            }

        position = self._positions[position_key]

        if order["offset"] == "OPEN":
            position["volume"] += order["volume"]
            position["price"] = order["price"]
        else:
            position["volume"] -= order["volume"]

        # 发布成交事件
        trade = {
            "trade_id": f"TRADE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "order_id": order_id,
            "symbol": order["symbol"],
            "exchange": order["exchange"],
            "direction": order["direction"],
            "offset": order["offset"],
            "price": order["price"],
            "volume": order["volume"],
            "trade_time": datetime.now().isoformat(),
        }

        event = self.create_event("trading", "trade.filled", trade)
        await self.publish_event(event)

        logger.info(f"Trade filled: {trade['trade_id']}")


async def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} - {message}",
    )

    # 从环境变量获取配置
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")

    # 创建NATS适配器
    adapter = NATSAdapter()
    await adapter.connect([nats_url])
    logger.info(f"Connected to NATS at {nats_url}")

    # 创建服务
    service = SimpleTradingService("vnpy-trading-demo", adapter)

    # 启动服务
    await service.start()
    logger.info("Trading service started")

    # 保持运行
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await service.stop()
        await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
