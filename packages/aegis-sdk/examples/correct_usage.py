"""
正确使用 AegisSDK 的示例代码

这个文件展示了如何正确使用SDK的公开API，避免直接访问私有成员。
"""

import asyncio

from aegis_sdk import Event, NATSAdapter, Service


class TradingService(Service):
    """正确实现的交易服务示例"""

    async def on_start(self):
        """服务启动时注册处理器"""

        # 注册RPC方法 - 使用装饰器（推荐）
        @self.rpc("send_order")
        async def send_order(params: dict) -> dict:
            order_id = await self.process_order(params)

            # ✅ 正确：使用公开的 publish_event 方法
            await self.publish_event(
                self.create_event(
                    "trading",
                    "order.submitted",
                    {
                        "order_id": order_id,
                        "symbol": params["symbol"],
                        "price": params["price"],
                        "volume": params["volume"],
                    },
                )
            )

            # ❌ 错误：不要直接访问 _bus
            # await self._bus.publish_event(...)  # 不要这样做！

            return {"success": True, "order_id": order_id}

        # 订阅事件 - 使用装饰器（推荐）
        @self.subscribe("market.tick.*")
        async def handle_tick(event: Event):
            symbol = event.payload.get("symbol")
            price = event.payload.get("price")
            print(f"Tick: {symbol} @ {price}")

            # 如果需要发布响应事件
            if price > 100:
                # ✅ 正确：使用 create_event + publish_event
                event = self.create_event(
                    "trading",
                    "price.alert",
                    {"symbol": symbol, "price": price, "alert": "HIGH_PRICE"},
                )
                await self.publish_event(event)

    async def process_order(self, params: dict) -> str:
        """处理订单的业务逻辑"""
        # 验证参数
        if params.get("volume", 0) <= 0:
            raise ValueError("Volume must be positive")

        # 生成订单ID
        import uuid

        order_id = f"ORD-{uuid.uuid4().hex[:8]}"

        # 调用其他服务
        # ✅ 正确：使用 call_rpc 方法
        account_info = await self.call_rpc(
            self.create_rpc_request("account-service", "get_balance", {"currency": "USD"})
        )

        # ❌ 错误：不要直接使用 _bus.call_rpc
        # await self._bus.call_rpc(...)  # 不要这样做！

        return order_id

    async def handle_command_example(self):
        """命令处理示例"""
        # ✅ 正确：使用 send_command 方法
        result = await self.send_command(
            self.create_command(
                "risk-service",
                "calculate_risk",
                {"portfolio_id": "123"},
                priority=CommandPriority.HIGH,
            )
        )

        # ❌ 错误：不要直接访问 _bus.send_command
        # await self._bus.send_command(...)  # 不要这样做！


async def main():
    """主函数 - 展示服务启动的正确方式"""

    # 方式1：使用 quick_start（最简单）
    from aegis_sdk import quick_start

    service = await quick_start("trading-service")

    # 方式2：自定义配置（生产环境）
    adapter = NATSAdapter()
    await adapter.connect(["nats://localhost:4222"])

    service = TradingService(
        "trading-service", adapter, version="1.0.0", registry_ttl=30, heartbeat_interval=10
    )

    # 启动服务
    await service.start()

    # 演示：发布一个测试事件
    await service.publish_event(
        service.create_event(
            "system", "service.ready", {"service": "trading-service", "version": "1.0.0"}
        )
    )

    # 保持运行
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        await service.stop()
        await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(main())


"""
总结：SDK公开API使用指南

✅ 应该使用的方法：
- service.create_event()      # 创建事件对象
- service.publish_event()     # 发布事件
- service.call_rpc()          # RPC调用
- service.send_command()      # 发送命令
- service.create_event()      # 创建事件对象
- service.create_rpc_request() # 创建RPC请求
- service.create_command()    # 创建命令对象

❌ 不应该使用的：
- service._bus               # 私有成员，不要直接访问
- service._registry          # 私有成员，不要直接访问
- service._discovery         # 私有成员，不要直接访问
- service._metrics           # 私有成员，不要直接访问

记住：使用公开API可以确保代码的稳定性和向后兼容性！
"""
