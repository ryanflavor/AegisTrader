"""
VNPy Trading Demo Service
使用OpenCTP 7x24环境进行交易，通过AegisSDK接收交易指令
"""

import asyncio
import os
import signal
import sys
from datetime import datetime
from threading import Thread
from typing import Any

from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.infrastructure import NATSAdapter
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
from vnpy.event import Event, EventEngine
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import (
    AccountData,
    CancelRequest,
    ContractData,
    OrderData,
    OrderRequest,
    PositionData,
    TradeData,
)
from vnpy_ctp import CtpGateway


class OrderCommand(BaseModel):
    """下单命令"""

    symbol: str
    exchange: str
    direction: str  # LONG/SHORT
    offset: str  # OPEN/CLOSE/CLOSETODAY/CLOSEYESTERDAY
    order_type: str = "LIMIT"  # LIMIT/MARKET
    price: float
    volume: int
    reference: str | None = None


class OrderInfo(BaseModel):
    """订单信息"""

    order_id: str
    symbol: str
    exchange: str
    direction: str
    offset: str
    price: float
    volume: int
    traded: int
    status: str
    time: datetime
    reference: str | None = None


class TradeInfo(BaseModel):
    """成交信息"""

    trade_id: str
    order_id: str
    symbol: str
    exchange: str
    direction: str
    offset: str
    price: float
    volume: int
    time: datetime


class PositionInfo(BaseModel):
    """持仓信息"""

    symbol: str
    exchange: str
    direction: str
    volume: int
    frozen: int
    price: float
    pnl: float
    yd_volume: int


class VnpyTradingService(SingleActiveService):
    """交易服务 - 单活跃模式，接收SDK指令执行交易"""

    def __init__(self, message_bus: NATSAdapter):
        # 使用单活跃服务，组名为trading-group
        super().__init__("vnpy-trading-demo", message_bus)
        self.vnpy_engine = None
        self.event_engine = None
        self.gateway_name = "CTP"
        self.is_connected = False

        # 订单映射
        self.order_map: dict[str, OrderData] = {}
        self.reference_map: dict[str, str] = {}  # reference -> vnpy_orderid

    async def on_start(self):
        """服务启动时初始化vnpy"""
        logger.info("Starting VNPy trading service...")

        # 订阅行情事件
        await self.subscribe_event("market", "tick.*", self.handle_market_tick)

        # 初始化vnpy引擎
        self.event_engine = EventEngine()
        self.vnpy_engine = MainEngine(self.event_engine)

        # 添加CTP网关
        self.vnpy_engine.add_gateway(CtpGateway)

        # 注册事件处理
        self._register_event_handlers()

        # 在单独线程启动vnpy事件引擎
        vnpy_thread = Thread(target=self._start_vnpy_engine)
        vnpy_thread.daemon = True
        vnpy_thread.start()

        # 等待vnpy启动
        await asyncio.sleep(2)

        # 连接到OpenCTP
        await self._connect_gateway()

        # 注册RPC方法
        await self.register_rpc_method("send_order", self.handle_send_order)
        await self.register_rpc_method("cancel_order", self.handle_cancel_order)
        await self.register_rpc_method("get_positions", self.handle_get_positions)
        await self.register_rpc_method("get_account", self.handle_get_account)
        await self.register_rpc_method("get_orders", self.handle_get_orders)

        logger.info("VNPy trading service started successfully")

    def _start_vnpy_engine(self):
        """在单独线程运行vnpy事件引擎"""
        # MainEngine已经自动启动了event_engine
        logger.info("VNPy event engine thread started")

    def _register_event_handlers(self):
        """注册vnpy事件处理器"""
        # 交易相关事件
        self.event_engine.register("order", self._on_order)
        self.event_engine.register("trade", self._on_trade)
        self.event_engine.register("position", self._on_position)
        self.event_engine.register("account", self._on_account)
        self.event_engine.register("contract", self._on_contract)

        # 日志事件
        self.event_engine.register("log", self._on_log)
        self.event_engine.register("error", self._on_error)

    async def _connect_gateway(self):
        """连接到OpenCTP"""
        setting = {
            "用户名": os.getenv("CTP_USER_ID", "13805"),
            "密码": os.getenv("CTP_PASSWORD", ""),
            "经纪商代码": os.getenv("CTP_BROKER_ID", "9999"),
            "交易服务器": os.getenv("CTP_TD_ADDRESS", "tcp://180.168.146.187:10202"),
            "行情服务器": os.getenv("CTP_MD_ADDRESS", "tcp://180.168.146.187:10212"),
            "产品名称": os.getenv("CTP_APP_ID", "simnow_client_test"),
            "授权编码": os.getenv("CTP_AUTH_CODE", "0000000000000000"),
        }

        logger.info(f"Connecting to OpenCTP with user: {setting['用户名']}")
        self.vnpy_engine.connect(setting, self.gateway_name)

        # 等待连接
        await asyncio.sleep(5)
        self.is_connected = True

    async def handle_market_tick(self, event_data: dict[str, Any]):
        """处理行情事件（来自行情服务）"""
        symbol = event_data.get("symbol")
        price = event_data.get("last_price")
        logger.debug(f"Received market tick: {symbol} @ {price}")

    async def handle_send_order(self, command: dict[str, Any]) -> dict[str, Any]:
        """处理下单请求"""
        try:
            order_cmd = OrderCommand(**command)
            logger.info(
                f"Sending order: {order_cmd.symbol} {order_cmd.direction} {order_cmd.volume}@{order_cmd.price}"
            )

            # 转换为vnpy格式
            req = OrderRequest(
                symbol=order_cmd.symbol,
                exchange=Exchange(order_cmd.exchange),
                direction=Direction(order_cmd.direction),
                type=OrderType(order_cmd.order_type),
                volume=order_cmd.volume,
                price=order_cmd.price,
                offset=Offset(order_cmd.offset),
            )

            # 发送订单
            vnpy_orderid = self.vnpy_engine.send_order(req, self.gateway_name)

            if vnpy_orderid:
                # 保存reference映射
                if order_cmd.reference:
                    self.reference_map[order_cmd.reference] = vnpy_orderid

                return {"success": True, "order_id": vnpy_orderid, "reference": order_cmd.reference}
            else:
                return {"success": False, "error": "Failed to send order"}

        except Exception as e:
            logger.error(f"Error sending order: {e}")
            return {"success": False, "error": str(e)}

    async def handle_cancel_order(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理撤单请求"""
        try:
            order_id = params.get("order_id")
            reference = params.get("reference")

            # 通过reference查找order_id
            if reference and not order_id:
                order_id = self.reference_map.get(reference)

            if not order_id:
                return {"success": False, "error": "Order not found"}

            # 获取订单信息
            order = self.order_map.get(order_id)
            if not order:
                return {"success": False, "error": "Order not found in cache"}

            # 创建撤单请求
            req = CancelRequest(orderid=order.orderid, symbol=order.symbol, exchange=order.exchange)

            # 发送撤单
            self.vnpy_engine.cancel_order(req, self.gateway_name)

            return {"success": True, "order_id": order_id}

        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return {"success": False, "error": str(e)}

    async def handle_get_positions(self, params: dict) -> list[dict[str, Any]]:
        """获取持仓信息"""
        positions = self.vnpy_engine.get_all_positions()

        result = []
        for pos in positions:
            if pos.volume > 0:  # 只返回有持仓的
                pos_info = PositionInfo(
                    symbol=pos.symbol,
                    exchange=pos.exchange.value,
                    direction=pos.direction.value,
                    volume=pos.volume,
                    frozen=pos.frozen,
                    price=pos.price,
                    pnl=pos.pnl,
                    yd_volume=pos.yd_volume,
                )
                result.append(pos_info.model_dump())

        return result

    async def handle_get_account(self, params: dict) -> dict[str, Any]:
        """获取账户信息"""
        accounts = self.vnpy_engine.get_all_accounts()

        if accounts:
            account = accounts[0]  # CTP通常只有一个账户
            return {
                "balance": account.balance,
                "available": account.available,
                "frozen": account.frozen,
                "commission": account.commission,
                "margin": account.margin,
                "close_profit": account.close_profit,
                "holding_profit": account.holding_profit,
            }
        else:
            return {}

    async def handle_get_orders(self, params: dict) -> list[dict[str, Any]]:
        """获取当前订单"""
        orders = self.vnpy_engine.get_all_active_orders()

        result = []
        for order in orders:
            order_info = OrderInfo(
                order_id=order.orderid,
                symbol=order.symbol,
                exchange=order.exchange.value,
                direction=order.direction.value,
                offset=order.offset.value,
                price=order.price,
                volume=order.volume,
                traded=order.traded,
                status=order.status.value,
                time=order.datetime or datetime.now(),
            )
            result.append(order_info.model_dump())

        return result

    def _on_order(self, event: Event):
        """处理订单事件"""
        order: OrderData = event.data

        # 缓存订单
        self.order_map[order.orderid] = order

        # 转换为SDK事件
        order_info = OrderInfo(
            order_id=order.orderid,
            symbol=order.symbol,
            exchange=order.exchange.value,
            direction=order.direction.value,
            offset=order.offset.value,
            price=order.price,
            volume=order.volume,
            traded=order.traded,
            status=order.status.value,
            time=order.datetime or datetime.now(),
        )

        # 查找reference
        for ref, oid in self.reference_map.items():
            if oid == order.orderid:
                order_info.reference = ref
                break

        # 发布订单更新事件
        asyncio.run_coroutine_threadsafe(
            self.publish_event(
                f"trading.order.{order.status.value.lower()}", order_info.model_dump()
            ),
            self.loop,
        )

    def _on_trade(self, event: Event):
        """处理成交事件"""
        trade: TradeData = event.data

        # 转换为SDK事件
        trade_info = TradeInfo(
            trade_id=trade.tradeid,
            order_id=trade.orderid,
            symbol=trade.symbol,
            exchange=trade.exchange.value,
            direction=trade.direction.value,
            offset=trade.offset.value,
            price=trade.price,
            volume=trade.volume,
            time=trade.datetime or datetime.now(),
        )

        # 发布成交事件
        asyncio.run_coroutine_threadsafe(
            self.publish_event("trading.trade.filled", trade_info.model_dump()), self.loop
        )

    def _on_position(self, event: Event):
        """处理持仓事件"""
        position: PositionData = event.data
        logger.debug(
            f"Position update: {position.symbol} {position.direction.value} {position.volume}"
        )

    def _on_account(self, event: Event):
        """处理账户事件"""
        account: AccountData = event.data
        logger.debug(f"Account update: Balance={account.balance}, Available={account.available}")

    def _on_contract(self, event: Event):
        """处理合约事件"""
        contract: ContractData = event.data
        logger.debug(f"Contract: {contract.symbol}.{contract.exchange.value}")

    def _on_log(self, event: Event):
        """处理vnpy日志事件"""
        log = event.data
        logger.info(f"[VNPy] {log.msg}")

    def _on_error(self, event: Event):
        """处理vnpy错误事件"""
        error = event.data
        logger.error(f"[VNPy Error] {error.msg}")

    async def on_stop(self):
        """服务停止时清理"""
        logger.info("Stopping VNPy trading service...")

        if self.vnpy_engine:
            self.vnpy_engine.close()

        if self.event_engine:
            self.event_engine.stop()

        logger.info("VNPy trading service stopped")


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

    # 创建NATS适配器
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    adapter = NATSAdapter()
    await adapter.connect([nats_url])
    logger.info(f"Connected to NATS at {nats_url}")

    # 创建并启动服务
    service = VnpyTradingService(adapter)
    await service.start()

    # 保持运行
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await service.stop()
        await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
