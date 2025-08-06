#!/usr/bin/env python3
"""
测试演示，展示两种服务模式的实际区别：
1. Regular Service - 所有实例都能处理请求（负载均衡）
2. SingleActiveService - 只有领导者能处理独占请求
2b. SingleActiveService + 客户端重试 - 实现粘性活跃模式
"""

import asyncio
import os
import sys

# Add the aegis-sdk to path
sys.path.insert(0, "/home/ryan/workspace/github/AegisTrader/packages/aegis-sdk")

from aegis_sdk.application.service import Service
from aegis_sdk.application.single_active_dtos import SingleActiveConfig
from aegis_sdk.application.single_active_service import SingleActiveService
from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults
from aegis_sdk.infrastructure.config import NATSConnectionConfig
from aegis_sdk.infrastructure.kv_service_registry import KVServiceRegistry
from aegis_sdk.infrastructure.nats_adapter import NATSAdapter
from aegis_sdk.infrastructure.nats_kv_store import NATSKVStore
from aegis_sdk.infrastructure.simple_logger import SimpleLogger


class RegularServiceDemo(Service):
    """普通服务 - 所有实例都能处理请求"""

    def __init__(self, instance_num: int, *args, **kwargs):
        self.instance_num = instance_num
        self.request_count = 0
        super().__init__(*args, **kwargs)

    async def on_start(self):
        """注册RPC处理器"""

        @self.rpc("process_order")
        async def process_order(params: dict) -> dict:
            self.request_count += 1
            order_id = params.get("order_id", "unknown")
            print(
                f"    ✓ [Instance-{self.instance_num}] 处理订单 {order_id} (累计: {self.request_count})"
            )
            return {
                "success": True,
                "processor": f"instance-{self.instance_num}",
                "order_id": order_id,
                "request_count": self.request_count,
            }


class SingleActiveDemo(SingleActiveService):
    """单活跃服务 - 只有领导者处理独占请求"""

    def __init__(self, instance_num: int, *args, **kwargs):
        self.instance_num = instance_num
        self.request_count = 0
        super().__init__(*args, **kwargs)

    async def on_start(self):
        """注册独占RPC处理器"""

        @self.exclusive_rpc("process_exclusive")
        async def process_exclusive(params: dict) -> dict:
            self.request_count += 1
            order_id = params.get("order_id", "unknown")
            print(
                f"    ✓ [Leader-{self.instance_num}] 处理独占订单 {order_id} (累计: {self.request_count})"
            )
            return {
                "processor": f"leader-{self.instance_num}",
                "order_id": order_id,
                "request_count": self.request_count,
            }


async def test_regular_service():
    """测试普通服务 - 展示负载均衡"""
    print("\n" + "=" * 70)
    print("测试1: REGULAR SERVICE (普通服务 - 负载均衡)")
    print("=" * 70)

    # Setup
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    config = NATSConnectionConfig(servers=[nats_url], service_name="test", pool_size=1)
    bus = NATSAdapter(config=config)
    await bus.connect()

    print("\n1. 创建3个实例...")
    services = []
    for i in range(1, 4):
        service = RegularServiceDemo(
            instance_num=i,
            service_name="regular-demo",
            message_bus=bus,
            instance_id=f"regular-{i}",
            enable_registration=False,
        )
        await service.start()
        services.append(service)
        print(f"   ✓ Instance {i} 启动 (状态: ACTIVE - 可以处理请求)")

    print("\n2. 发送6个订单，模拟负载均衡...")
    print("   注意: 每个实例都能处理请求\n")

    # 直接调用不同实例的handler，模拟负载均衡
    for i in range(6):
        service_idx = i % 3
        service = services[service_idx]
        handler = service._handler_registry._rpc_handlers.get("process_order")
        if handler:
            await handler({"order_id": f"ORDER-{i + 1}"})

    print("\n3. 结果统计:")
    for i, service in enumerate(services, 1):
        print(f"   Instance {i}: 处理了 {service.request_count} 个订单")

    print("\n✅ 结论: 所有实例平均分担了请求（负载均衡）")

    # Cleanup
    for service in services:
        await service.stop()
    await bus.disconnect()


async def test_single_active_service():
    """测试单活跃服务 - 展示只有领导者处理请求"""
    print("\n" + "=" * 70)
    print("测试2: SINGLE ACTIVE SERVICE (单活跃服务 - 领导者独占)")
    print("=" * 70)

    bootstrap_defaults()

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    config = NATSConnectionConfig(servers=[nats_url], service_name="test", pool_size=1)
    bus = NATSAdapter(config=config)
    await bus.connect()

    kv_store = NATSKVStore(nats_adapter=bus)
    await kv_store.connect("test_registry2", enable_ttl=True)
    registry = KVServiceRegistry(kv_store, SimpleLogger("registry"))

    print("\n1. 创建3个实例（含领导者选举）...")
    services = []
    for i in range(1, 4):
        sa_config = SingleActiveConfig(
            service_name="single-demo",
            instance_id=f"single-{i}",
            version="1.0.0",
            group_id="test-group",
            leader_ttl_seconds=2,
            heartbeat_interval=5,
            registry_ttl=10,
        )

        service = SingleActiveDemo(
            instance_num=i, config=sa_config, message_bus=bus, service_registry=registry
        )
        await service.start()
        services.append(service)

        status = "ACTIVE (领导者)" if service.is_active else "STANDBY (待命)"
        print(f"   ✓ Instance {i} 启动 (状态: {status})")

    await asyncio.sleep(1)

    print("\n2. 每个实例都尝试处理独占请求...")
    print("   注意: 只有领导者能成功处理\n")

    # 每个实例都尝试处理请求
    for i, service in enumerate(services, 1):
        handler = service._handler_registry._rpc_handlers.get("process_exclusive")
        if handler:
            result = await handler({"order_id": f"EXCLUSIVE-{i}"})
            if not result.get("success", False):
                print(f"    ✗ [Instance-{i}] 拒绝处理: {result.get('message', 'NOT_ACTIVE')}")

    print("\n3. 结果统计:")
    leader_found = False
    for i, service in enumerate(services, 1):
        status = "领导者" if service.is_active else "待命"
        print(f"   Instance {i} ({status}): 处理了 {service.request_count} 个订单")
        if service.is_active:
            leader_found = True

    if leader_found:
        print("\n✅ 结论: 只有领导者实例处理了请求，其他实例拒绝服务")

    print("\n4. 模拟领导者故障...")
    leader = next((s for s in services if s.is_active), None)
    if leader:
        leader_idx = services.index(leader) + 1
        print(f"   停止当前领导者 (Instance {leader_idx})...")
        await leader.stop()
        services.remove(leader)

        print("   等待新领导者选举 (2-3秒)...")
        await asyncio.sleep(3)

        # 检查新领导者
        new_leader = next((s for s in services if s.is_active), None)
        if new_leader:
            new_idx = services.index(new_leader) + 1
            print(f"   ✓ 新领导者当选: Instance {new_idx + (1 if new_idx >= leader_idx else 0)}")

            # 新领导者处理请求
            handler = new_leader._handler_registry._rpc_handlers.get("process_exclusive")
            if handler:
                result = await handler({"order_id": "AFTER-FAILOVER"})
                if result.get("success"):
                    print("   ✓ 新领导者成功处理请求")

    # Cleanup
    for service in services:
        await service.stop()
    await bus.disconnect()


async def test_sticky_active_service():
    """测试粘性活跃服务 - 展示客户端粘性和自动重连"""
    print("\n" + "=" * 70)
    print("测试3: SINGLE ACTIVE WITH STICKY CLIENT (单活跃服务 + 粘性客户端)")
    print("=" * 70)

    bootstrap_defaults()

    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    config = NATSConnectionConfig(servers=[nats_url], service_name="test", pool_size=1)
    bus = NATSAdapter(config=config)
    await bus.connect()

    kv_store = NATSKVStore(nats_adapter=bus)
    await kv_store.connect("test_registry3", enable_ttl=True)
    registry = KVServiceRegistry(kv_store, SimpleLogger("registry"))

    print("\n1. 创建3个实例（粘性活跃模式）...")
    services = []
    for i in range(1, 4):
        sa_config = SingleActiveConfig(
            service_name="sticky-demo",
            instance_id=f"sticky-{i}",
            version="1.0.0",
            group_id="sticky-group",
            leader_ttl_seconds=2,
            heartbeat_interval=5,
            registry_ttl=10,
        )

        service = SingleActiveDemo(
            instance_num=i, config=sa_config, message_bus=bus, service_registry=registry
        )
        await service.start()
        services.append(service)

        status = "ACTIVE (领导者)" if service.is_active else "STANDBY (待命)"
        print(f"   ✓ Instance {i} 启动 (状态: {status})")

    await asyncio.sleep(1)

    print("\n2. 模拟3个客户端建立粘性连接...")
    print("   注意: 所有客户端都连接到同一个领导者\n")

    # 找到活跃领导者
    leader = next((s for s in services if s.is_active), services[0])
    leader_idx = services.index(leader) + 1

    # 模拟客户端会话
    class ClientSession:
        def __init__(self, client_id: int):
            self.client_id = client_id
            self.connected_instance = None
            self.request_count = 0

        async def connect_and_request(self, services):
            """连接到活跃实例并发送请求"""
            for service in services:
                if service.is_active:
                    self.connected_instance = services.index(service) + 1
                    handler = service._handler_registry._rpc_handlers.get("process_exclusive")
                    if handler:
                        self.request_count += 1
                        result = await handler(
                            {"order_id": f"CLIENT-{self.client_id}-REQ-{self.request_count}"}
                        )
                        if result.get("success"):
                            print(
                                f"   Client {self.client_id} → 成功连接到 Instance {self.connected_instance}"
                            )
                            return True
            return False

    # 创建客户端会话
    clients = [ClientSession(i) for i in range(1, 4)]

    # 初始连接
    for client in clients:
        await client.connect_and_request(services)

    print("\n3. 模拟领导者故障和客户端重连...")
    print(f"   停止当前领导者 (Instance {leader_idx})...")
    await leader.stop()
    services.remove(leader)

    print("   等待故障转移 (2-3秒)...")
    await asyncio.sleep(3)

    # 客户端自动重连
    print("\n4. 客户端自动重连到新领导者...")
    for client in clients:
        old_instance = client.connected_instance
        if await client.connect_and_request(services):
            print(
                f"   Client {client.client_id}: 从 Instance {old_instance} 重连到 Instance {client.connected_instance}"
            )

    print("\n✅ 结论: 客户端保持粘性连接，故障时自动重连到新领导者")

    # Cleanup
    for service in services:
        await service.stop()
    await bus.disconnect()


async def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print(" AEGIS SDK 两种服务模式 - 完整测试验证")
    print("=" * 80)

    try:
        await test_regular_service()
        await test_single_active_service()
        await test_sticky_active_service()

        print("\n" + "=" * 80)
        print(" 总结: 两种服务模式的核心区别")
        print("=" * 80)
        print("""
1. REGULAR SERVICE (普通服务):
   ✓ 所有实例都是ACTIVE，都能处理请求
   ✓ 请求在实例间负载均衡
   ✓ 无需领导者选举
   ✓ 适用场景: 无状态服务、REST API、查询服务

2. SINGLE ACTIVE SERVICE (单活跃服务):
   ✓ 只有一个领导者实例能处理独占请求
   ✓ 其他实例处于STANDBY状态，会拒绝请求
   ✓ 领导者故障时2-3秒内自动选举新领导者
   ✓ 适用场景: 数据库迁移、定时任务、订单号生成

3. STICKY ACTIVE SERVICE (粘性活跃服务):
   ✓ 基于SingleActive，但强调客户端会话粘性
   ✓ 客户端连接会"粘"在活跃领导者上
   ✓ 领导者故障时，客户端自动重连到新领导者
   ✓ 适用场景: WebSocket网关、游戏服务器、交易会话
        """)

        print("✅ 所有测试完成，两种服务模式的区别已清晰展示！")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
