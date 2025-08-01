"""Sticky Single Active Pattern - Working Implementation."""

import asyncio
import contextlib
import json
import time

import nats
from nats.errors import TimeoutError as NATSTimeoutError


class StickySingleActiveService:
    """粘性单活跃服务 - 确保同一个实例持续处理直到失效."""

    def __init__(self, service_name: str, instance_id: str):
        self.service_name = service_name
        self.instance_id = instance_id
        self.nc = None
        self.js = None

        # 活跃状态
        self.is_active = False
        self.last_heartbeat = time.time()
        self.active_instance = None

        # 业务计数
        self.processed_count = 0
        self.running = True

    async def connect(self, servers: list[str]):
        """连接 NATS."""
        self.nc = await nats.connect(servers=servers)
        self.js = self.nc.jetstream()

        # 创建命令流
        try:
            await self.js.stream_info(f"{self.service_name}_COMMANDS")
            print(f"✅ Stream {self.service_name}_COMMANDS already exists")
        except:
            await self.js.add_stream(
                name=f"{self.service_name}_COMMANDS",
                subjects=[f"{self.service_name}.commands.>"],
                retention="workqueue",
            )
            print(f"✅ Created stream {self.service_name}_COMMANDS")

        print(f"✅ {self.instance_id} connected")

    async def start(self):
        """启动服务和选举."""
        # 订阅心跳
        await self.nc.subscribe(
            f"{self.service_name}.heartbeat", cb=self._handle_heartbeat
        )

        # 启动选举循环
        election_task = asyncio.create_task(self._election_loop())

        # 启动处理循环
        process_task = asyncio.create_task(self._process_loop())

        try:
            await asyncio.gather(election_task, process_task)
        except asyncio.CancelledError:
            print(f"🛑 {self.instance_id} stopped")

    async def stop(self):
        """停止服务."""
        self.running = False
        if self.nc:
            await self.nc.close()

    async def _handle_heartbeat(self, msg):
        """处理心跳消息."""
        try:
            data = json.loads(msg.data.decode())

            if data["instance_id"] != self.instance_id:
                # 其他实例是活跃的
                self.active_instance = data["instance_id"]
                self.last_heartbeat = time.time()

                # 如果我们之前是活跃的，现在让位
                if self.is_active:
                    print(f"🔄 {self.instance_id} 检测到 {data['instance_id']} 是活跃的，让位")
                    self.is_active = False
        except Exception as e:
            print(f"❌ Heartbeat error: {e}")

    async def _election_loop(self):
        """选举循环 - 决定谁是活跃实例."""
        await asyncio.sleep(2)  # 初始等待

        while self.running:
            try:
                current_time = time.time()

                # 如果超过 5 秒没有心跳，尝试成为活跃
                if not self.is_active and (current_time - self.last_heartbeat > 5):
                    print(f"🗳️ {self.instance_id} 未检测到活跃实例，尝试成为活跃")

                    # 等待随机时间避免竞争
                    await asyncio.sleep(0.1 * hash(self.instance_id) % 10 / 10)

                    # 再次检查是否有其他实例已经活跃
                    if current_time - self.last_heartbeat > 5:
                        self.is_active = True
                        self.active_instance = self.instance_id
                        print(f"👑 {self.instance_id} 成为活跃实例!")

                # 如果是活跃的，发送心跳
                if self.is_active:
                    heartbeat = {
                        "instance_id": self.instance_id,
                        "timestamp": current_time,
                        "processed": self.processed_count,
                    }
                    await self.nc.publish(
                        f"{self.service_name}.heartbeat", json.dumps(heartbeat).encode()
                    )

                await asyncio.sleep(2)

            except Exception as e:
                print(f"❌ Election error: {e}")
                await asyncio.sleep(1)

    async def _process_loop(self):
        """处理循环 - 只有活跃实例才处理消息."""
        # 使用 pull_subscribe 而不是 pull_subscribe_bind
        # 这会自动创建消费者如果不存在
        consumer = await self.js.pull_subscribe(
            f"{self.service_name}.commands.>",
            durable=f"{self.service_name}-processor",
            stream=f"{self.service_name}_COMMANDS",
        )

        print(f"🎯 {self.instance_id} 准备处理命令")

        while self.running:
            try:
                # 只有活跃实例才拉取消息
                if self.is_active:
                    # 拉取单个消息
                    try:
                        msgs = await consumer.fetch(1, timeout=1)

                        for msg in msgs:
                            # 双重检查还是不是活跃的
                            if not self.is_active:
                                # 不再是活跃的，拒绝消息让其他实例处理
                                await msg.nak()
                                break

                            # 处理消息
                            data = json.loads(msg.data.decode())
                            self.processed_count += 1

                            print(
                                f"📦 {self.instance_id} 处理命令 #{self.processed_count}: {data}"
                            )

                            # 模拟处理时间
                            await asyncio.sleep(0.5)

                            # 确认消息
                            await msg.ack()

                    except NATSTimeoutError:
                        # 没有消息，正常情况
                        pass
                else:
                    # 非活跃状态，等待
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ Process error: {e}")
                import traceback

                traceback.print_exc()
                await asyncio.sleep(1)


async def send_commands(service_name: str, servers: list[str], count: int = 20):
    """发送测试命令."""
    nc = await nats.connect(servers=servers)
    js = nc.jetstream()

    print(f"\n📤 发送 {count} 个测试命令...")

    for i in range(count):
        command = {
            "cmd_id": f"CMD-{int(time.time() * 1000)}-{i}",
            "action": "process_order" if i % 2 == 0 else "check_status",
            "seq": i + 1,
        }

        await js.publish(f"{service_name}.commands.new", json.dumps(command).encode())

        if i < 5 or i % 5 == 0:
            print(f"  → 发送命令 {i + 1}/{count}")

        await asyncio.sleep(0.1)

    await nc.close()
    print("📤 所有命令已发送\n")


async def demo():
    """运行演示."""
    servers = ["nats://localhost:4222"]
    service_name = "sticky-order-service"  # 使用不同的服务名避免冲突

    # 清理旧的流
    try:
        nc = await nats.connect(servers=servers)
        js = nc.jetstream()
        try:
            await js.delete_stream(f"{service_name}_COMMANDS")
            print("🧹 Cleaned old stream")
        except:
            pass
        await nc.close()
    except:
        pass

    # 启动 2 个实例（简化演示）
    instances = []
    tasks = []

    for i in range(1, 3):
        instance = StickySingleActiveService(service_name, f"instance-{i}")
        await instance.connect(servers)
        instances.append(instance)

        # 启动实例
        task = asyncio.create_task(instance.start())
        tasks.append(task)

    print("\n=== 等待选举完成 ===")
    await asyncio.sleep(8)

    # 显示当前活跃实例
    active_count = 0
    for instance in instances:
        if instance.is_active:
            print(f"📍 当前活跃实例: {instance.instance_id}")
            active_count += 1

    if active_count == 0:
        print("❌ 没有活跃实例!")
    elif active_count > 1:
        print(f"⚠️  有 {active_count} 个活跃实例!")

    # 发送命令
    await send_commands(service_name, servers, 15)

    # 运行一段时间
    print("\n=== 处理命令中... ===")
    await asyncio.sleep(10)

    # 显示中间统计
    print("\n=== 中间统计 ===")
    for instance in instances:
        if instance.processed_count > 0:
            print(f"{instance.instance_id}: 已处理 {instance.processed_count} 个命令")

    # 模拟活跃实例故障
    print("\n=== 模拟活跃实例故障 ===")
    for instance in instances:
        if instance.is_active:
            print(f"💥 停止活跃实例: {instance.instance_id}")
            instance.is_active = False
            instance.running = False
            break

    # 等待重新选举
    await asyncio.sleep(8)

    # 显示新的活跃实例
    for instance in instances:
        if instance.is_active:
            print(f"📍 新的活跃实例: {instance.instance_id}")
            break

    # 发送更多命令
    await send_commands(service_name, servers, 10)

    # 继续运行
    await asyncio.sleep(8)

    # 显示最终统计
    print("\n=== 最终统计 ===")
    total_processed = 0
    for instance in instances:
        print(f"{instance.instance_id}: 处理了 {instance.processed_count} 个命令")
        total_processed += instance.processed_count
    print(f"总共处理: {total_processed} 个命令")
    print("预期处理: 25 个命令")

    # 清理
    for instance in instances:
        instance.running = False

    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    for instance in instances:
        await instance.stop()


if __name__ == "__main__":
    print("=== 粘性单活跃模式演示 (Working Version) ===\n")
    print("特点:")
    print("1. 只有一个实例是活跃的")
    print("2. 活跃实例会持续处理所有请求")
    print("3. 活跃实例失效后，其他实例接管")
    print("4. 使用 JetStream 保证消息不丢失\n")

    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\n\n用户中断，退出...")
