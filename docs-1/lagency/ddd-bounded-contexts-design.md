# AegisTrader DDD限界上下文设计文档

基于vnpy原生类型系统的领域驱动设计

## 1. vnpy核心类型映射

### 1.1 枚举类型 (从vnpy.trader.constant导入)
```python
from vnpy.trader.constant import (
    Direction,      # 多(LONG) / 空(SHORT) / 净(NET)
    Offset,         # 开(OPEN) / 平(CLOSE) / 平今(CLOSETODAY) / 平昨(CLOSEYESTERDAY)
    Status,         # 提交中 / 未成交 / 部分成交 / 全部成交 / 已撤销 / 拒单
    Product,        # 期货 / 期权 / 股票 等
    OrderType,      # 限价 / 市价 / STOP / FAK / FOK
    Exchange,       # CFFEX / SHFE / DCE / CZCE 等
    Interval,       # 1m / 1h / d / w / tick
)
```

### 1.2 数据类型 (从vnpy.trader.object导入)
```python
from vnpy.trader.object import (
    TickData,       # Tick行情数据
    BarData,        # K线数据
    OrderData,      # 订单数据
    TradeData,      # 成交数据
    PositionData,   # 持仓数据
    AccountData,    # 账户数据
    ContractData,   # 合约数据
    OrderRequest,   # 订单请求
    CancelRequest,  # 撤单请求
)
```

## 2. 限界上下文设计

### 2.1 交易网关上下文 (Trading Gateway Context)

**职责**: 模拟CTP网关，处理订单撮合和执行，完全兼容vnpy_ctp接口

```python
# domain/gateway_context/aggregates.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from vnpy.trader.object import OrderData, TradeData, OrderRequest
from vnpy.trader.constant import Status, Direction, Offset

@dataclass
class OrderBook:
    """订单簿聚合根 - 管理买卖盘队列"""
    symbol: str
    exchange: Exchange

    # 使用vnpy的OrderData作为订单实体
    bid_orders: List[OrderData] = field(default_factory=list)  # 买盘队列
    ask_orders: List[OrderData] = field(default_factory=list)  # 卖盘队列

    def add_order(self, order: OrderData) -> None:
        """添加订单到订单簿"""
        if order.direction == Direction.LONG:
            self._insert_bid_order(order)
        else:
            self._insert_ask_order(order)

    def match_order(self, order: OrderData) -> List[TradeData]:
        """撮合订单 - 价格时间优先"""
        trades = []

        if order.direction == Direction.LONG:
            # 买单匹配卖盘
            while self.ask_orders and order.volume > order.traded:
                best_ask = self.ask_orders[0]
                if order.price >= best_ask.price:
                    trade = self._execute_match(order, best_ask)
                    trades.append(trade)
                else:
                    break
        else:
            # 卖单匹配买盘
            while self.bid_orders and order.volume > order.traded:
                best_bid = self.bid_orders[0]
                if order.price <= best_bid.price:
                    trade = self._execute_match(order, best_bid)
                    trades.append(trade)
                else:
                    break

        return trades

@dataclass
class TradingGateway:
    """交易网关聚合根 - 模拟CTP网关"""
    gateway_name: str = "SIMULATED_CTP"

    # 使用vnpy原生类型
    order_books: Dict[str, OrderBook] = field(default_factory=dict)
    active_orders: Dict[str, OrderData] = field(default_factory=dict)
    positions: Dict[str, PositionData] = field(default_factory=dict)

    def send_order(self, req: OrderRequest) -> str:
        """发送订单 - 兼容vnpy_ctp接口"""
        # 生成订单ID
        orderid = self._generate_orderid()

        # 创建OrderData - 使用vnpy原生类型
        order = req.create_order_data(orderid, self.gateway_name)
        order.status = Status.SUBMITTING

        # 添加到活动订单
        self.active_orders[orderid] = order

        # 提交到撮合
        self._submit_to_matching(order)

        return orderid

    def cancel_order(self, req: CancelRequest) -> None:
        """撤销订单"""
        if req.orderid in self.active_orders:
            order = self.active_orders[req.orderid]
            if order.status in [Status.NOTTRADED, Status.PARTTRADED]:
                order.status = Status.CANCELLED
                self._remove_from_orderbook(order)

    def on_trade(self, trade: TradeData) -> None:
        """成交回调 - 兼容vnpy回调接口"""
        # 更新订单状态
        if trade.orderid in self.active_orders:
            order = self.active_orders[trade.orderid]
            order.traded += trade.volume

            if order.traded >= order.volume:
                order.status = Status.ALLTRADED
            else:
                order.status = Status.PARTTRADED

        # 更新持仓
        self._update_position(trade)
```

### 2.2 订单管理上下文 (Order Management Context)

**职责**: 管理订单生命周期，实现SingleActiveService模式

```python
# domain/order_context/aggregates.py
from vnpy.trader.object import OrderData, OrderRequest, TradeData
from vnpy.trader.constant import Status, Direction, Offset

@dataclass
class OrderAggregate:
    """订单聚合根 - 管理单个订单的完整生命周期"""

    order: OrderData  # 使用vnpy的OrderData
    trades: List[TradeData] = field(default_factory=list)

    # 领域事件
    events: List[DomainEvent] = field(default_factory=list)

    @classmethod
    def create_from_request(cls, req: OrderRequest, orderid: str, gateway: str) -> 'OrderAggregate':
        """从请求创建订单"""
        order = req.create_order_data(orderid, gateway)
        order.status = Status.SUBMITTING

        aggregate = cls(order=order)
        aggregate._raise_event(OrderSubmittedEvent(orderid))
        return aggregate

    def on_trade(self, trade: TradeData) -> None:
        """处理成交"""
        # 状态验证
        if self.order.status not in [Status.NOTTRADED, Status.PARTTRADED]:
            raise InvalidOrderStateError(f"订单状态{self.order.status}不能成交")

        self.trades.append(trade)
        self.order.traded += trade.volume

        # 更新状态
        if self.order.traded >= self.order.volume:
            self.order.status = Status.ALLTRADED
            self._raise_event(OrderFilledEvent(self.order.orderid))
        else:
            self.order.status = Status.PARTTRADED
            self._raise_event(OrderPartiallyFilledEvent(self.order.orderid))

    def cancel(self) -> None:
        """撤销订单"""
        if self.order.status == Status.ALLTRADED:
            raise CannotCancelFilledOrderError()

        if self.order.status in [Status.NOTTRADED, Status.PARTTRADED]:
            self.order.status = Status.CANCELLED
            self._raise_event(OrderCancelledEvent(self.order.orderid))

# domain/order_context/services.py
class OrderManagementService(SingleActiveService):
    """订单管理服务 - SingleActive模式"""

    async def submit_order(self, req: OrderRequest) -> str:
        """提交订单 - 只有Active节点处理"""
        if not self.is_active():
            raise NotActiveError("请重试到活跃节点")

        # 风险检查
        if not await self._validate_risk(req):
            raise RiskValidationError()

        # 创建订单聚合
        orderid = self._generate_orderid()
        order_agg = OrderAggregate.create_from_request(req, orderid, self.gateway_name)

        # 发送到网关
        await self.gateway.send_order(req)

        # 保存聚合
        await self.repository.save(order_agg)

        # 发布事件
        for event in order_agg.collect_events():
            await self.event_bus.publish(event)

        return orderid
```

### 2.3 市场数据上下文 (Market Data Context)

**职责**: 生成和分发市场数据，完全使用vnpy数据结构

```python
# domain/market_context/aggregates.py
from vnpy.trader.object import TickData, BarData
from vnpy.trader.constant import Exchange, Interval

@dataclass
class MarketDataStream:
    """市场数据流聚合根"""
    symbol: str
    exchange: Exchange
    gateway_name: str = "MARKET_SIM"

    # 当前市场状态
    last_tick: Optional[TickData] = None
    current_bar: Optional[BarData] = None

    def generate_tick(self) -> TickData:
        """生成Tick数据 - 使用vnpy的TickData"""
        tick = TickData(
            symbol=self.symbol,
            exchange=self.exchange,
            datetime=datetime.now(),
            gateway_name=self.gateway_name,

            # 生成五档行情
            bid_price_1=self._generate_price(),
            bid_volume_1=self._generate_volume(),
            ask_price_1=self._generate_price(),
            ask_volume_1=self._generate_volume(),

            last_price=self._generate_price(),
            volume=self._generate_volume(),
        )

        self.last_tick = tick
        return tick

    def generate_bar(self, interval: Interval) -> BarData:
        """生成K线数据 - 使用vnpy的BarData"""
        bar = BarData(
            symbol=self.symbol,
            exchange=self.exchange,
            datetime=datetime.now(),
            interval=interval,
            gateway_name=self.gateway_name,

            open_price=self._generate_price(),
            high_price=self._generate_price(),
            low_price=self._generate_price(),
            close_price=self._generate_price(),
            volume=self._generate_volume(),
        )

        self.current_bar = bar
        return bar

# domain/market_context/services.py
class MarketDataService:
    """市场数据服务"""

    async def publish_tick(self, tick: TickData) -> None:
        """发布Tick数据"""
        topic = f"market.tick.{tick.vt_symbol}"
        await self.event_bus.publish(topic, tick)

    async def publish_bar(self, bar: BarData) -> None:
        """发布K线数据"""
        topic = f"market.bar.{bar.interval.value}.{bar.vt_symbol}"
        await self.event_bus.publish(topic, bar)
```

### 2.4 持仓风险上下文 (Position & Risk Context)

**职责**: 管理持仓和风险，使用vnpy的PositionData

```python
# domain/risk_context/aggregates.py
from vnpy.trader.object import PositionData, TradeData
from vnpy.trader.constant import Direction

@dataclass
class RiskProfile:
    """风险画像聚合根"""
    account_id: str
    gateway_name: str

    # 使用vnpy的PositionData
    positions: Dict[str, PositionData] = field(default_factory=dict)

    # 风险指标
    total_exposure: float = 0
    total_pnl: float = 0
    margin_used: float = 0
    margin_available: float = 0

    def update_position(self, trade: TradeData) -> None:
        """更新持仓 - 基于成交"""
        key = f"{trade.vt_symbol}.{trade.direction.value}"

        if key not in self.positions:
            self.positions[key] = PositionData(
                symbol=trade.symbol,
                exchange=trade.exchange,
                direction=trade.direction,
                gateway_name=self.gateway_name,
                volume=0,
                price=0,
            )

        position = self.positions[key]

        # 更新持仓量和均价
        if trade.offset == Offset.OPEN:
            # 开仓
            total_cost = position.volume * position.price + trade.volume * trade.price
            position.volume += trade.volume
            position.price = total_cost / position.volume if position.volume > 0 else 0
        else:
            # 平仓
            position.volume -= trade.volume
            if position.volume <= 0:
                del self.positions[key]

    def calculate_pnl(self, current_prices: Dict[str, float]) -> float:
        """计算盈亏"""
        total_pnl = 0
        for position in self.positions.values():
            current_price = current_prices.get(position.vt_symbol, position.price)

            if position.direction == Direction.LONG:
                position.pnl = (current_price - position.price) * position.volume
            else:
                position.pnl = (position.price - current_price) * position.volume

            total_pnl += position.pnl

        self.total_pnl = total_pnl
        return total_pnl

    def check_risk_limits(self) -> List[RiskViolation]:
        """检查风险限制"""
        violations = []

        # 检查总暴露
        if self.total_exposure > self.max_exposure:
            violations.append(ExposureLimitViolation(self.total_exposure))

        # 检查保证金
        if self.margin_available < self.min_margin:
            violations.append(MarginViolation(self.margin_available))

        return violations
```

### 2.5 算法执行上下文 (Algorithm Execution Context)

**职责**: 执行算法订单（TWAP/VWAP等）

```python
# domain/algo_context/aggregates.py
@dataclass
class AlgoOrder:
    """算法订单聚合根"""
    algo_id: str
    algo_type: str  # "TWAP", "VWAP", "ICEBERG"

    # 使用vnpy的OrderRequest作为基础
    original_request: OrderRequest

    # 算法参数
    start_time: datetime
    end_time: datetime
    interval: int  # 执行间隔（秒）

    # 执行状态
    total_volume: float
    executed_volume: float = 0
    child_orders: List[OrderData] = field(default_factory=list)

    def generate_slice_order(self) -> Optional[OrderRequest]:
        """生成切片订单"""
        if self.executed_volume >= self.total_volume:
            return None

        # 计算本次切片大小
        remaining = self.total_volume - self.executed_volume
        time_progress = self._calculate_time_progress()

        if self.algo_type == "TWAP":
            # 时间加权平均
            slice_volume = self._calculate_twap_slice(remaining, time_progress)
        elif self.algo_type == "VWAP":
            # 成交量加权平均
            slice_volume = self._calculate_vwap_slice(remaining)
        else:
            slice_volume = min(remaining, self.slice_size)

        # 创建切片订单请求
        slice_request = OrderRequest(
            symbol=self.original_request.symbol,
            exchange=self.original_request.exchange,
            direction=self.original_request.direction,
            type=self.original_request.type,
            volume=slice_volume,
            price=self._calculate_slice_price(),
            offset=self.original_request.offset,
            reference=f"ALGO_{self.algo_id}",
        )

        return slice_request
```

## 3. 上下文映射关系

```yaml
context_map:
  # 客户-供应商关系
  order_management -> trading_gateway:
    relationship: Customer-Supplier
    integration: RPC (订单管理调用网关服务)

  # 发布-订阅关系
  market_data -> ALL:
    relationship: Publisher-Subscriber
    integration: Event (市场数据广播)
    topics:
      - market.tick.{symbol}
      - market.bar.{interval}.{symbol}

  # 共享内核
  risk_monitoring <-> order_management:
    relationship: Shared-Kernel
    shared: PositionData, risk validation rules

  # 竞争消费
  algo_execution:
    subscription_mode: COMPETE
    topics:
      - orders.algo.*
```

## 4. 领域事件定义

```python
# domain/events.py
from dataclasses import dataclass
from datetime import datetime
from vnpy.trader.object import OrderData, TradeData

@dataclass
class DomainEvent:
    """领域事件基类"""
    event_id: str
    timestamp: datetime
    aggregate_id: str

# 订单事件
@dataclass
class OrderSubmittedEvent(DomainEvent):
    order: OrderData

@dataclass
class OrderFilledEvent(DomainEvent):
    order: OrderData
    trade: TradeData

@dataclass
class OrderCancelledEvent(DomainEvent):
    order: OrderData

# 市场事件
@dataclass
class TickReceivedEvent(DomainEvent):
    tick: TickData

@dataclass
class BarGeneratedEvent(DomainEvent):
    bar: BarData

# 风险事件
@dataclass
class RiskLimitBreachedEvent(DomainEvent):
    risk_type: str
    current_value: float
    limit_value: float

@dataclass
class MarginCallEvent(DomainEvent):
    account_id: str
    required_margin: float
    available_margin: float
```

## 5. 仓储接口定义

```python
# ports/repositories.py
from abc import ABC, abstractmethod
from typing import Optional, List
from vnpy.trader.object import OrderData, TradeData, PositionData

class OrderRepository(ABC):
    """订单仓储接口"""

    @abstractmethod
    async def save(self, order: OrderData) -> None:
        """保存订单"""
        pass

    @abstractmethod
    async def find_by_id(self, orderid: str) -> Optional[OrderData]:
        """根据ID查找订单"""
        pass

    @abstractmethod
    async def find_active_orders(self) -> List[OrderData]:
        """查找活动订单"""
        pass

class PositionRepository(ABC):
    """持仓仓储接口"""

    @abstractmethod
    async def save(self, position: PositionData) -> None:
        """保存持仓"""
        pass

    @abstractmethod
    async def find_by_symbol(self, symbol: str) -> List[PositionData]:
        """根据合约查找持仓"""
        pass
```

## 6. 实施建议

### 6.1 优先级排序
1. **Phase 1**: 实现Trading Gateway Context（核心撮合引擎）
2. **Phase 2**: 实现Order Management Context（订单生命周期）
3. **Phase 3**: 实现Market Data Context（行情生成）
4. **Phase 4**: 实现Risk Context（风险管理）
5. **Phase 5**: 实现Algorithm Context（算法交易）

### 6.2 技术选型
- **持久化**: 使用Event Sourcing存储订单事件流
- **消息总线**: 继续使用NATS JetStream
- **状态管理**: Redis用于缓存活动订单和持仓
- **监控**: 使用现有的Monitor API/UI

### 6.3 测试策略
- 单元测试: 每个聚合根的业务逻辑
- 集成测试: 上下文间的交互
- 端到端测试: 完整交易流程
- 性能测试: 撮合引擎的吞吐量

## 7. 与vnpy_ctp的兼容性

通过完全采用vnpy的类型系统，我们确保了：
1. **数据结构兼容**: 直接使用vnpy的OrderData, TradeData等
2. **状态机兼容**: 使用相同的Status枚举（SUBMITTING → NOTTRADED → PARTTRADED → ALLTRADED）
3. **接口兼容**: Gateway接口与vnpy_ctp保持一致
4. **回调兼容**: on_order, on_trade等回调签名相同

这种设计允许未来无缝切换到真实的CTP网关，只需要替换Gateway实现即可。
