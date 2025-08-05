# VNPy Integration Step-by-Step Plan

## 概述
将vnpy集成到AegisSDK中，创建三个核心服务：
- MarketDataService：行情数据分发
- TradingService：交易执行（单活跃模式）
- AlgoService：算法策略运行

## Phase 1: 基础准备（1-2天）

### Step 1.1: 环境设置
```bash
# 1. 创建服务目录结构
mkdir -p apps/market-data-service
mkdir -p apps/trading-service
mkdir -p apps/algo-service

# 2. 创建共享合约包
mkdir -p packages/trading-contracts
```

### Step 1.2: 安装vnpy并测试
```python
# 创建简单测试脚本验证vnpy安装
# test_vnpy.py
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
print("VNPy import successful!")
```

### Step 1.3: 研究vnpy事件系统
- 理解vnpy的EventEngine
- 学习TickData、OrderData、TradeData等数据结构
- 测试vnpy的模拟交易环境

## Phase 2: 创建适配层（2-3天）

### Step 2.1: VNPy-SDK事件适配器
```python
# packages/aegis-sdk/aegis_sdk/adapters/vnpy_adapter.py
class VnpyEventAdapter:
    """将vnpy事件转换为SDK事件"""
    def __init__(self, sdk_service):
        self.service = sdk_service

    def on_tick(self, tick: TickData):
        # 转换为SDK事件格式
        self.service.publish_event("market.tick", {
            "symbol": tick.symbol,
            "price": tick.last_price,
            # ...
        })
```

### Step 2.2: 数据模型映射
```python
# packages/trading-contracts/models.py
from pydantic import BaseModel

class SDKTickData(BaseModel):
    """SDK格式的行情数据"""
    symbol: str
    last_price: float
    volume: int
    # 映射vnpy的TickData
```

## Phase 3: MarketDataService实现（3-4天）

### Step 3.1: 基础服务结构
```python
# apps/market-data-service/main.py
from aegis_sdk import Service
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine

class MarketDataService(Service):
    def __init__(self):
        super().__init__("market-data-service")
        self.event_engine = EventEngine()
        self.main_engine = MainEngine(self.event_engine)
```

### Step 3.2: 实现行情订阅
- 连接到模拟/测试行情源
- 订阅指定合约
- 将行情广播给其他服务

### Step 3.3: 测试与优化
- 单元测试
- 性能测试（延迟、吞吐量）
- K8s部署测试

## Phase 4: TradingService实现（4-5天）

### Step 4.1: 单活跃模式实现
```python
# 使用SDK的SingleActiveService
from aegis_sdk import SingleActiveService

class TradingService(SingleActiveService):
    def __init__(self):
        super().__init__("trading-service", "trading-group")
```

### Step 4.2: 交易接口实现
- 下单RPC接口
- 撤单RPC接口
- 查询持仓/委托
- 订单状态更新事件

### Step 4.3: 风控集成
- 资金检查
- 持仓限制
- 下单频率控制

## Phase 5: AlgoService实现（3-4天）

### Step 5.1: 策略框架
```python
from vnpy.app.cta_strategy import CtaTemplate

class SDKStrategyTemplate(CtaTemplate):
    """适配SDK的策略模板"""
    def __init__(self, service):
        self.service = service
```

### Step 5.2: 策略管理
- 策略加载/卸载
- 参数配置
- 状态监控

### Step 5.3: 示例策略
- 简单的均线策略
- 网格交易策略

## Phase 6: 集成测试（2-3天）

### Step 6.1: 端到端测试
- 三个服务协同工作
- 模拟完整交易流程
- 故障恢复测试

### Step 6.2: 性能基准
- 行情延迟测试
- 下单延迟测试
- 系统吞吐量测试

### Step 6.3: K8s部署
- 更新Helm charts
- 配置资源限制
- 监控指标集成

## 关键技术点

### 1. 事件循环集成
```python
# 需要协调vnpy和SDK的事件循环
import asyncio
from threading import Thread

class EventLoopBridge:
    def __init__(self, vnpy_engine, sdk_service):
        self.vnpy_engine = vnpy_engine
        self.sdk_service = sdk_service

    def start(self):
        # vnpy使用线程
        vnpy_thread = Thread(target=self.vnpy_engine.start)
        vnpy_thread.start()

        # SDK使用asyncio
        asyncio.run(self.sdk_service.start())
```

### 2. 数据序列化
- vnpy对象 → Pydantic模型 → JSON
- 考虑性能影响

### 3. 错误处理
- 网络断线重连
- 交易所拒单处理
- 服务故障转移

## 简化方案（推荐先实现）

如果觉得完整方案太复杂，可以先实现简化版：

### Option 1: 只实现MarketDataService
- 专注于行情分发
- 使用模拟数据源
- 验证vnpy集成可行性

### Option 2: Mock交易环境
- 使用vnpy的模拟交易功能
- 不连接真实交易所
- 专注于架构验证

### Option 3: 单体Demo
- 先在一个进程中集成所有功能
- 验证vnpy和SDK能协同工作
- 之后再拆分服务

## 下一步行动

1. **选择实施方案**：
   - 完整方案（~3周）
   - 简化方案（~1周）
   - 单体Demo（~3天）

2. **准备开发环境**：
   - 安装vnpy
   - 设置模拟账户
   - 准备测试数据

3. **开始编码**：
   - 从最简单的部分开始
   - 逐步增加功能
   - 持续测试

您想从哪个方案开始？我建议先做单体Demo验证可行性。
