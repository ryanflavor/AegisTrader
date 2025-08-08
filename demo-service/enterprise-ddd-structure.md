# 企业级 DDD 项目结构对比

## 🏗️ 你提议的企业级 DDD 架构

```
enterprise-trading-service/
│
├── application/      # 应用层 - 组合领域对象和基础设施实现
│   ├── commands.py   # 命令对象（写操作）
│   ├── queries.py    # 查询对象（读操作）
│   └── handlers.py   # 命令/查询处理器
│
├── domain/           # 领域层 - 核心业务逻辑
│   ├── entities.py      # 实体（有身份的对象）
│   ├── value_objects.py # 值对象（无身份的对象）
│   ├── repositories.py  # 仓储接口
│   └── services.py      # 领域服务
│
├── infra/            # 基础设施层 - 技术实现
│   ├── persistence.py   # 数据持久化
│   ├── messaging.py     # 消息传递
│   └── adapters.py      # 外部服务适配器
│
├── crossdomain/      # 防腐层 - 领域间隔离
│   ├── translators.py      # 数据转换器
│   └── anti_corruption.py  # 防腐层实现
│
├── pkg/              # 纯工具包 - 无外部依赖
│   ├── utils.py         # 工具函数
│   └── validators.py    # 验证器
│
└── types/            # 类型定义 - 共享类型
    ├── dto.py           # 数据传输对象
    └── interfaces.py    # 接口定义
```

## 🎯 优势分析

### 1. **防腐层（Anti-Corruption Layer）**
- **作用**：保护领域模型不被外部系统污染
- **场景**：
  - 与遗留系统集成
  - 与第三方服务交互
  - 微服务间通信

### 2. **CQRS 模式支持**
- **Commands**: 修改状态的操作
- **Queries**: 读取状态的操作
- **好处**：读写分离，优化性能

### 3. **更细粒度的领域建模**
- **Entities**: 有唯一标识的对象（如：Order, User）
- **Value Objects**: 不可变的值对象（如：Money, Email）
- **好处**：更精确的业务建模

### 4. **纯函数工具包**
- **特点**：无副作用，无外部依赖
- **好处**：高度可测试，可复用

## 📋 使用示例

### 创建企业级DDD项目：

```bash
./run-aegis-cli.sh bootstrap \
  --project-name enterprise-trading-service \
  --template enterprise_ddd \
  --environment production \
  --include-tests \
  --include-docker \
  --include-k8s
```

### 标准项目 vs 企业级DDD：

| 特性 | 标准架构 | 企业级DDD |
|-----|---------|-----------|
| 目录结构 | 4-5个目录 | 6个专业目录 |
| 领域建模 | 简单models | Entities + Value Objects |
| 命令查询 | 混合处理 | CQRS分离 |
| 防腐层 | 无 | 专门的crossdomain层 |
| 工具函数 | 分散 | 集中在pkg |
| 类型定义 | 分散 | 集中在types |

## 🔧 适用场景

### 选择标准架构：
- 小型项目
- 快速原型
- 简单CRUD应用
- 团队DDD经验不足

### 选择企业级DDD：
- 复杂业务逻辑
- 需要与多个外部系统集成
- 长期维护的大型项目
- 需要领域驱动设计
- 微服务架构

## 💡 实施建议

1. **从标准架构开始**，随着业务复杂度增加逐步迁移到企业级DDD
2. **防腐层不是必须的**，只在需要隔离外部系统时添加
3. **CQRS可以逐步实施**，先从简单的读写分离开始
4. **保持pkg层的纯净**，只放置无副作用的工具函数
