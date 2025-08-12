# AegisSDK Developer Tools

快速创建和部署微服务的开发工具包。

## 🚀 快速开始

### 1. 安装
```bash
pip install aegis-sdk-dev
```

### 2. 创建新项目（5秒）
```bash
# 使用已安装的命令
aegis-bootstrap --project-name my-service --template enterprise_ddd --output-dir ./

# 或使用项目根目录的便捷脚本
./aegis bootstrap --project-name my-service --template enterprise_ddd --output-dir ./
```

### 3. 部署到 Kubernetes（3分钟）
```bash
cd my-service
make deploy-to-kind  # 自动构建、测试、部署
```

### 4. 验证
```bash
kubectl get pods -n aegis-trader
# my-service-xxxxx  1/1  Running  0  30s
```

## 📦 生成的完整项目结构

```
my-service/
├── domain/              # 领域层（DDD核心）
│   ├── entities.py      # 领域实体
│   ├── value_objects.py # 值对象
│   ├── repositories.py  # 仓储接口
│   ├── services.py      # 领域服务
│   └── events.py        # 领域事件
├── application/         # 应用层（用例编排）
│   ├── commands.py      # CQRS命令
│   ├── queries.py       # CQRS查询
│   ├── handlers.py      # 命令/查询处理器
│   └── dto.py          # 数据传输对象
├── infra/              # 基础设施层（技术实现）
│   ├── adapters.py      # 外部服务适配器
│   ├── persistence.py   # 持久化实现
│   ├── messaging.py     # 消息实现（NATS）
│   └── cache.py        # 缓存层
├── crossdomain/        # 防腐层
│   ├── translators.py   # 数据转换器
│   └── anti_corruption.py # 防腐外观
├── app_types/          # 类型定义
│   ├── dto.py          # 共享DTO
│   ├── interfaces.py   # 接口定义
│   └── enums.py        # 枚举类型
├── pkg/                # 工具包
│   ├── utils.py        # 通用工具
│   ├── validators.py   # 验证器
│   └── helpers.py      # 辅助函数
├── tests/              # 测试套件
│   ├── unit/           # 单元测试
│   └── integration/    # 集成测试
├── k8s/                # Kubernetes部署
│   ├── templates/      # Helm模板
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   ├── ingress.yaml
│   │   ├── serviceaccount.yaml
│   │   └── _helpers.tpl
│   ├── Chart.yaml      # Helm chart元数据
│   ├── values.yaml     # 默认配置
│   ├── values-dev.yaml # 开发环境配置
│   └── values-prod.yaml # 生产环境配置
├── main.py             # 服务入口（异步架构）
├── Makefile            # DevOps自动化命令
├── Dockerfile          # 多阶段构建（含代理）
├── docker-compose.yml  # 本地开发环境
├── pyproject.toml      # Python 3.13依赖
├── requirements.txt    # pip兼容依赖
├── .env.example        # 环境变量示例
├── .gitignore         # Git忽略规则
├── .dockerignore      # Docker忽略规则
├── .python-version    # Python版本（uv）
└── README.md          # 项目文档
```

## 🛠️ 核心命令

```bash
make test-local      # 本地验证（Docker构建前的预检）
make docker-build    # 构建镜像（自动加载代理配置）
make deploy-to-kind  # 一键部署到 Kind 集群
make helm-upgrade    # 更新部署（使用版本化镜像）
```

## ⚙️ 代理配置

如果需要代理，在项目根目录创建 `.env`：
```bash
HTTP_PROXY=http://your-proxy:port
HTTPS_PROXY=http://your-proxy:port
NO_PROXY=localhost,127.0.0.1,nats
```

## 🔧 关键特性

✅ **预验证机制** - `test-local` 在构建前捕获错误
✅ **版本化部署** - 使用时间戳版本，避免 ImagePullBackOff
✅ **代理自动配置** - 从根目录 `.env` 加载
✅ **健康检查管理** - 默认禁用，避免无端点时的重启
✅ **完整 Helm 模板** - 包含所有必要的辅助函数

## 📝 常见问题

### Pod 状态 ImagePullBackOff
**原因**：使用了不存在的 'latest' 标签
**解决**：模板已修复，自动使用版本化镜像

### Pod 状态 CrashLoopBackOff
**原因**：健康检查失败或代码错误
**解决**：
1. 运行 `make test-local` 检查代码
2. 健康检查已默认禁用

### Docker 构建失败（代理环境）
**原因**：未配置代理
**解决**：在根目录创建 `.env` 文件配置代理

## 🎯 设计理念

- **6天开发周期** - 从想法到生产部署
- **开箱即用** - 生成的代码可直接运行
- **生产就绪** - 包含所有 DevOps 最佳实践
- **DDD架构** - 企业级六边形架构

## 📊 CLI 工具

```bash
aegis-bootstrap   # 创建新项目
aegis-validate    # 验证配置
aegis-quickstart  # 交互式向导
```

## 💡 开发经验总结

### JSON 序列化处理
**问题**：在 echo-service-ddd 中发现重复实现了 datetime 序列化
**解决**：使用 SDK 提供的 `aegis_sdk.infrastructure.serialization.serialize_dict`
**教训**：避免在服务层重复实现 SDK 已提供的底层功能

### Task 6 验证成功
- ✅ Kubernetes 部署配置完整可用
- ✅ Helm charts 结构正确，支持多环境
- ✅ 所有 RPC 端点测试通过
- ✅ 使用 SDK 序列化工具后，datetime 处理正常

---

**版本**: 0.1.0 | **最后优化**: 2025-08-11
