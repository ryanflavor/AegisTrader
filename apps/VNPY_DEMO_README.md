# VNPy Demo 使用说明

## 概述

这是一个基于vnpy和AegisSDK的交易系统Demo，包含两个独立的服务：
- **vnpy-market-demo**: 行情服务，从OpenCTP获取实时行情
- **vnpy-trading-demo**: 交易服务，执行交易指令（单活跃模式）

两个服务通过AegisSDK进行通信。

## 环境准备

### 1. 安装Python依赖

```bash
# 需要Python 3.10+
python --version

# 安装vnpy（如果需要全局安装）
pip install vnpy vnpy-ctp
```

### 2. 启动NATS

```bash
# 使用Docker启动NATS
docker run -d --name nats -p 4222:4222 nats:latest

# 或者使用已有的K8s环境
kubectl port-forward -n aegis-trader svc/aegis-trader-nats 4222:4222
```

### 3. 配置OpenCTP账号

编辑各服务的`.env`文件：

```bash
# 复制示例配置
cp vnpy-market-demo/.env.example vnpy-market-demo/.env
cp vnpy-trading-demo/.env.example vnpy-trading-demo/.env

# 编辑.env文件，添加OpenCTP密码
# CTP_USER_ID=13805
# CTP_PASSWORD=your_password_here
```

## 快速启动

使用提供的启动脚本：

```bash
cd apps
./run-vnpy-demo.sh
```

选择操作：
1. 只启动行情服务
2. 只启动交易服务
3. 启动两个服务
4. 运行测试客户端
5. 停止所有服务

## 手动启动

### 启动行情服务

```bash
cd vnpy-market-demo
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 启动交易服务

```bash
cd vnpy-trading-demo
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 运行测试客户端

```bash
cd apps
python test-client.py
```

## 功能测试

测试客户端会自动执行以下测试：

1. **订阅行情**: 订阅rb2501、ag2501、au2501等合约
2. **获取账户信息**: 查询账户余额、可用资金等
3. **获取持仓**: 查询当前持仓
4. **下单测试**: 发送一个测试订单
5. **撤单测试**: 撤销刚才的订单

## 架构说明

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Test Client    │     │ Market Service  │     │ Trading Service │
│                 │     │                 │     │ (Single-Active) │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                        │
         │ RPC/Event             │                        │
         └───────────────────────┴────────────────────────┘
                                 │
                          ┌──────┴──────┐
                          │  AegisSDK   │
                          │    NATS     │
                          └─────────────┘
```

## 关键代码结构

### 行情服务
- 使用vnpy的EventEngine处理行情事件
- 将vnpy的TickData转换为SDK事件格式
- 通过SDK发布到`market.tick.{symbol}`主题

### 交易服务
- 继承SingleActiveService确保只有一个实例处理交易
- 接收SDK的RPC调用执行交易
- 将订单、成交事件发布到SDK

### SDK通信
- RPC调用：`send_order`, `cancel_order`, `get_positions`等
- 事件发布：`market.tick.*`, `trading.order.*`, `trading.trade.*`

## 注意事项

1. **OpenCTP环境**
   - 使用的是7×24小时环境
   - 账号：13805
   - 需要设置正确的密码

2. **合约代码格式**
   - vnpy格式：`rb2501.SHFE`
   - symbol部分：`rb2501`
   - 交易所部分：`SHFE`

3. **单活跃模式**
   - 交易服务使用SingleActiveService
   - 同时只有一个实例处理交易请求
   - 故障时自动切换到备份实例

4. **事件循环协调**
   - vnpy使用线程+回调模式
   - SDK使用asyncio
   - 通过`asyncio.run_coroutine_threadsafe`桥接

## 故障排查

1. **连接失败**
   - 检查NATS是否运行
   - 检查OpenCTP服务器地址
   - 确认账号密码正确

2. **没有行情**
   - 确认合约代码正确
   - 检查是否在交易时间
   - 查看vnpy日志输出

3. **下单失败**
   - 检查账户余额
   - 确认合约状态
   - 查看错误日志

## 下一步

1. **添加更多功能**
   - 策略管理
   - 风控检查
   - 历史数据查询

2. **生产环境部署**
   - 容器化
   - K8s部署
   - 监控告警

3. **性能优化**
   - 行情延迟优化
   - 批量下单
   - 内存数据库
