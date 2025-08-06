"""
VNPy Market Data Demo Service
使用OpenCTP 7x24环境获取行情数据，通过AegisSDK分发
"""

import asyncio
import os
import signal
import sys
from datetime import datetime
from threading import Thread
from typing import Any

from aegis_sdk import Service
from aegis_sdk.infrastructure import NATSAdapter
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
from vnpy.event import Event, EventEngine
from vnpy.trader.constant import Exchange
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import SubscribeRequest, TickData
from vnpy_ctp import CtpGateway


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


class VnpyMarketService(Service):
    """行情服务 - 从OpenCTP获取行情并通过SDK分发"""

    def __init__(self, message_bus: NATSAdapter):
        super().__init__("vnpy-market-demo", message_bus)
        self.vnpy_engine = None
        self.event_engine = None
        self.gateway_name = "CTP"
        self.subscribed_symbols = set()

    async def on_start(self):
        """服务启动时初始化vnpy"""
        logger.info("Starting VNPy market service...")

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
        await self.register_rpc_method("subscribe", self.handle_subscribe)
        await self.register_rpc_method("unsubscribe", self.handle_unsubscribe)
        await self.register_rpc_method("get_subscribed", self.handle_get_subscribed)

        logger.info("VNPy market service started successfully")

    def _start_vnpy_engine(self):
        """在单独线程运行vnpy事件引擎"""
        # MainEngine已经自动启动了event_engine
        logger.info("VNPy event engine thread started")

    def _register_event_handlers(self):
        """注册vnpy事件处理器"""
        # 注册行情事件处理
        self.event_engine.register("tick", self._on_tick)
        # 注册日志事件
        self.event_engine.register("log", self._on_log)
        # 注册错误事件
        self.event_engine.register("error", self._on_error)

    def _on_tick(self, event: Event):
        """处理vnpy行情事件"""
        tick: TickData = event.data

        # Log tick received
        logger.info(
            f"[TICK] {tick.symbol}.{tick.exchange.value} Price:{tick.last_price} Vol:{tick.volume}"
        )

        # 转换为SDK事件格式
        tick_event = MarketTickEvent(
            symbol=tick.symbol,
            exchange=tick.exchange.value,
            datetime=tick.datetime,
            last_price=tick.last_price,
            volume=tick.volume,
            bid_price_1=tick.bid_price_1,
            bid_volume_1=tick.bid_volume_1,
            ask_price_1=tick.ask_price_1,
            ask_volume_1=tick.ask_volume_1,
            open_interest=tick.open_interest,
        )

        # 通过SDK发布事件
        asyncio.run_coroutine_threadsafe(self._publish_tick_event(tick_event), self.loop)

    async def _publish_tick_event(self, tick_event: MarketTickEvent):
        """发布行情事件到SDK"""
        await self.publish_event(
            f"market.tick.{tick_event.symbol}", tick_event.model_dump(mode="json")
        )

    def _on_log(self, event: Event):
        """处理vnpy日志事件"""
        log = event.data
        logger.info(f"[VNPy] {log.msg}")

        # Check for connection status
        if "行情服务器连接成功" in log.msg or "交易服务器连接成功" in log.msg:
            logger.success(f"[VNPy Connected] {log.msg}")
        elif "登录成功" in log.msg:
            logger.success(f"[VNPy Login] {log.msg}")

    def _on_error(self, event: Event):
        """处理vnpy错误事件"""
        error = event.data
        logger.error(f"[VNPy Error] {error.msg}")

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

    async def handle_subscribe(self, params: dict) -> dict[str, Any]:
        """处理订阅请求"""
        logger.info(f"Received subscribe request with params: {params}")
        logger.info(f"Params type: {type(params)}")

        # Handle both direct params and nested params
        if isinstance(params, dict) and "params" in params:
            params = params["params"]

        symbols = params.get("symbols", [])
        logger.info(f"Extracted symbols: {symbols}")

        success = []
        failed = []

        for symbol in symbols:
            try:
                # 解析symbol格式: rb2501.SHFE
                parts = symbol.split(".")
                if len(parts) != 2:
                    failed.append(f"{symbol}: Invalid format")
                    continue

                vt_symbol = symbol
                symbol_code = parts[0]
                exchange_str = parts[1]

                # 转换交易所枚举
                exchange = Exchange(exchange_str)

                # 创建订阅请求
                req = SubscribeRequest(symbol=symbol_code, exchange=exchange)

                # 订阅行情
                self.vnpy_engine.subscribe(req, self.gateway_name)
                self.subscribed_symbols.add(vt_symbol)
                success.append(vt_symbol)

            except Exception as e:
                failed.append(f"{symbol}: {str(e)}")

        return {
            "success": success,
            "failed": failed,
            "total_subscribed": len(self.subscribed_symbols),
        }

    async def handle_unsubscribe(self, params: dict) -> dict[str, Any]:
        """处理取消订阅请求"""
        symbols = params.get("symbols", [])
        logger.info(f"Received unsubscribe request for symbols: {symbols}")

        for symbol in symbols:
            self.subscribed_symbols.discard(symbol)

        return {"unsubscribed": symbols, "total_subscribed": len(self.subscribed_symbols)}

    async def handle_get_subscribed(self, params: dict) -> list[str]:
        """获取当前订阅的合约列表"""
        return list(self.subscribed_symbols)

    async def on_stop(self):
        """服务停止时清理"""
        logger.info("Stopping VNPy market service...")

        if self.vnpy_engine:
            self.vnpy_engine.close()

        if self.event_engine:
            self.event_engine.stop()

        logger.info("VNPy market service stopped")


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
    service = VnpyMarketService(adapter)
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
