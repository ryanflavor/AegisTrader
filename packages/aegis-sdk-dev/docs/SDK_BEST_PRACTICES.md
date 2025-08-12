# AegisSDK 最佳实践 - 避免重复造轮子

## ❌ 常见错误：重新实现 SDK 已提供的功能

### 错误示例：手动实现服务基础设施
```python
# 不要这样做 - 826 行重复代码！
class ServiceRunner:
    async def _send_heartbeats(self, service_name: str, instance_id: str):
        # 手动实现心跳...

    async def run(self):
        # 手动管理 NATS 连接...
        # 手动处理信号...
        # 手动注册服务...
        # 手动清理资源...
```

### ✅ 正确做法：使用 SDK Service 类
```python
# 只需 40-80 行代码
from aegis_sdk.application.service import Service, ServiceConfig

service = Service(
    service_name=config.service_name,
    message_bus=nats,
    instance_id=config.instance_id,
    service_registry=registry,
    logger=SimpleLogger(service_name),
    heartbeat_interval=10.0,  # SDK 自动处理心跳
    enable_registration=True   # SDK 自动处理注册
)

# 注册业务逻辑
await service.register_rpc_method("echo", handle_echo)

# 启动服务 - SDK 处理所有基础设施
await service.start()
```

## 📦 SDK 已提供的功能（不要重新实现）

### 1. **服务生命周期管理**
- ✅ 使用: `Service.start()`, `Service.stop()`
- ❌ 避免: 自定义 ServiceRunner, 手动生命周期状态

### 2. **心跳和健康检查**
- ✅ 使用: `Service` 的 `heartbeat_interval` 参数
- ❌ 避免: 自定义 `_send_heartbeats()` 方法

### 3. **服务注册和发现**
- ✅ 使用: `KVServiceRegistry`, `enable_registration=True`
- ❌ 避免: 自定义注册逻辑，手动 KV 操作

### 4. **RPC 处理**
- ✅ 使用: `service.register_rpc_method()`
- ❌ 避免: 手动 NATS 订阅，自定义消息解析

### 5. **日志记录**
- ✅ 使用: `SimpleLogger` 或实现 `LoggerPort`
- ❌ 避免: 自定义 LoggingAdapter

### 6. **消息总线抽象**
- ✅ 使用: `NATSAdapter` 直接作为 `message_bus`
- ❌ 避免: 自定义 ServiceBusAdapter 包装器

### 7. **配置管理**
- ✅ 使用: `ServiceConfig` dataclass
- ❌ 避免: 自定义配置类

### 8. **错误处理和重试**
- ✅ 使用: SDK 内置的错误处理
- ❌ 避免: 每个服务自定义重试逻辑

## 🏗️ 正确的服务架构

### 精简的服务结构
```
my-service/
├── main.py              # 40-80 行：SDK Service 初始化 + RPC 注册
├── domain/              # 业务逻辑（保留 DDD）
│   ├── entities.py      # 领域实体
│   ├── services.py      # 领域服务
│   └── events.py        # 领域事件
├── application/         # 用例层（保留 DDD）
│   └── use_cases.py     # 业务用例
└── config.py           # 配置（可选）
```

### 不需要的文件（SDK 已提供）
```
❌ infra/factory.py        # SDK Service 替代
❌ infra/adapters.py       # SDK 已有所有适配器
❌ crossdomain/anti_corruption.py  # 除非真的需要
❌ pkg/utils.py            # 使用 SDK 工具
❌ types/interfaces.py     # 使用 SDK 端口
```

## 💡 扩展 SDK 的正确方式

### 1. **扩展而非替换**
```python
# 如果需要自定义行为，扩展 Service 类
class MyCustomService(Service):
    async def on_start(self):
        """自定义启动逻辑"""
        await super().on_start()
        # 添加自定义逻辑
```

### 2. **使用 SDK 端口接口**
```python
# 实现 SDK 定义的端口
from aegis_sdk.ports.logger import LoggerPort

class MyCustomLogger(LoggerPort):
    def log(self, level: str, message: str, **context):
        # 自定义日志实现
```

### 3. **利用 SDK 工具函数**
```python
from aegis_sdk.infrastructure.serialization import serialize_dict
from aegis_sdk.infrastructure.bootstrap import bootstrap_defaults

# 不要重新实现这些工具
```

## 📋 检查清单：是否在重复造轮子？

在编写代码前，检查以下内容：

- [ ] SDK Service 类是否已提供此功能？
- [ ] SDK 是否有现成的适配器/实现？
- [ ] 是否可以通过配置解决而非编码？
- [ ] 是否可以扩展 SDK 类而非重写？
- [ ] SDK 工具函数是否已存在？

## 🎯 模板生成器优化建议

### 当前问题
`simple_project_generator.py` 生成了错误的模式：
- 手动 NATS 连接管理
- 手动信号处理
- 手动生命周期管理

### 应该生成的模式
```python
# main.py 应该只有这些内容
async def main():
    # 1. 基础连接
    nats = NATSAdapter()
    await nats.connect(nats_url)

    # 2. 创建 SDK Service
    service = Service(...)

    # 3. 注册业务处理器
    await service.register_rpc_method("my_method", handle_my_method)

    # 4. 启动（SDK 处理一切）
    await service.start()
    await asyncio.Event().wait()
```

## 📊 对比：重复造轮子 vs 使用 SDK

| 功能 | 重复造轮子 | 使用 SDK | 节省代码 |
|------|------------|----------|---------|
| 服务基础设施 | 826 行 | 40 行 | 95% |
| 心跳管理 | 54 行 | 1 参数 | 98% |
| 生命周期 | 126 行 | 2 方法调用 | 98% |
| RPC 处理 | 133 行 | 1 方法调用 | 99% |
| 服务注册 | 77 行 | 1 参数 | 99% |
| **总计** | **1216 行** | **~50 行** | **96%** |

## 🚀 立即行动

1. **审查现有代码**：检查是否重复实现 SDK 功能
2. **重构 echo-service-ddd**：使用 `main_optimized.py` 作为参考
3. **更新模板生成器**：生成使用 SDK Service 的代码
4. **培训团队**：确保所有人了解 SDK 功能
5. **文档化**：记录 SDK 功能避免重复工作

---

**记住：SDK 已经解决了 80% 的基础设施问题，专注于业务逻辑即可！**
