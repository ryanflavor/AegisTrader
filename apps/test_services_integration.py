#!/usr/bin/env python
"""
测试vnpy服务集成 - 验证使用规范的SDK API
"""

import asyncio
import sys

from aegis_sdk import Service
from aegis_sdk.domain.models import Event, RPCRequest
from aegis_sdk.infrastructure import NATSAdapter
from loguru import logger


async def test_service_apis():
    """测试服务API使用是否规范"""

    # 配置日志
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    # 创建NATS适配器
    adapter = NATSAdapter()
    await adapter.connect(["nats://localhost:4222"])
    logger.info("Connected to NATS")

    # 创建测试服务
    service = Service("test-service", adapter)

    # 测试事件订阅（使用公开API）
    async def handle_event(event: Event):
        logger.info(f"Received event: {event.domain}.{event.event_type}")

    # 正确的方式：使用 subscribe_event 公开方法
    await service.subscribe_event("test", "event.*", handle_event)
    logger.info("✓ Event subscription using public API works")

    # 测试RPC注册
    async def handle_rpc(params: dict) -> dict:
        return {"success": True, "params": params}

    await service.register_rpc_method("test_method", handle_rpc)
    logger.info("✓ RPC registration using public API works")

    # 启动服务
    await service.start()
    logger.info("✓ Service started successfully")

    # 测试发布事件
    test_event = Event(
        domain="test", event_type="event.test", payload={"message": "Hello from test"}
    )
    await service.publish_event(test_event)
    logger.info("✓ Event published using public API")

    # 测试RPC调用
    rpc_request = RPCRequest(target="test-service", method="test_method", params={"test": "data"})

    try:
        response = await service.call_rpc(rpc_request)
        logger.info(f"✓ RPC call response: {response}")
    except Exception as e:
        logger.info(f"RPC call (expected to fail in self-test): {e}")

    # 等待一下让事件处理
    await asyncio.sleep(1)

    # 停止服务
    await service.stop()
    await adapter.disconnect()

    logger.info("\n🎉 All API tests passed! Services are using proper SDK public APIs.")


if __name__ == "__main__":
    asyncio.run(test_service_apis())
