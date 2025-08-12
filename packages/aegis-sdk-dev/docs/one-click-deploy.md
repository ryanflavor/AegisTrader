# 一键部署到 K8s 指南

## 快速开始

使用 aegis-sdk-dev 生成的项目支持一键部署到本地 K8s：

```bash
# 1. 生成新项目
aegis bootstrap -p my-service --template enterprise_ddd

# 2. 进入项目目录
cd my-service

# 3. 编写你的业务逻辑
vim main.py

# 4. 一键部署到 K8s
make deploy-to-kind
```

就这么简单！

## 工作原理

`make deploy-to-kind` 命令会自动执行以下步骤：

1. **构建 Docker 镜像**
   - 自动加载根目录的 .env 文件（包含代理设置）
   - 使用时间戳版本标签（如 20250811-101706）
   - 同时标记为 latest

2. **加载到 kind 集群**
   - 使用 `docker save | docker exec` 直接加载
   - 无需推送到远程仓库

3. **Helm 部署**
   - 自动创建命名空间
   - 使用正确的镜像版本
   - 等待部署完成

## 生成的文件结构

```
my-service/
├── main.py                 # 你的服务入口
├── Makefile               # 包含所有自动化命令
├── Dockerfile             # 优化的多阶段构建
├── docker-compose.yml     # 本地开发环境
├── .env.example           # 环境变量模板
├── k8s/                   # Kubernetes 配置
│   ├── Chart.yaml         # Helm chart 元数据
│   ├── values.yaml        # 默认配置
│   ├── values-dev.yaml    # 开发环境配置
│   ├── values-prod.yaml   # 生产环境配置
│   └── templates/         # Helm 模板
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── configmap.yaml
│       ├── ingress.yaml
│       └── _helpers.tpl
└── ...其他项目文件
```

## Makefile 命令详解

### 基础命令

```bash
# 构建 Docker 镜像（自动处理代理）
make docker-build

# 加载镜像到 kind 集群
make kind-load

# 部署到 K8s
make helm-install

# 一键完成所有步骤
make deploy-to-kind
```

### 高级命令

```bash
# 更新已部署的服务
make helm-upgrade

# 查看部署状态
kubectl get pods -n aegis-trader

# 查看日志
kubectl logs -f deployment/my-service -n aegis-trader

# 卸载服务
make helm-uninstall

# 本地测试（使用 docker-compose）
make docker-compose-up
```

## 环境要求

1. **Docker** - 用于构建镜像
2. **kind** - 本地 K8s 集群
3. **kubectl** - K8s 命令行工具
4. **Helm** - K8s 包管理器

### 安装 kind 集群

```bash
# 创建 kind 集群
kind create cluster --name aegis-local

# 验证集群
kubectl cluster-info
```

## 自定义配置

### 1. 修改服务配置

编辑 `k8s/values.yaml`：

```yaml
# 服务配置
service:
  name: my-service
  port: 80
  targetPort: 8080

# 资源限制
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 128Mi

# NATS 配置
nats:
  url: "nats://nats:4222"
```

### 2. 环境变量

编辑 `.env` 文件：

```bash
# 服务配置
SERVICE_NAME=my-service
SERVICE_PORT=8080
LOG_LEVEL=INFO

# NATS 配置
NATS_URL=nats://localhost:4222

# 代理配置（可选）
HTTP_PROXY=http://your-proxy:port
HTTPS_PROXY=http://your-proxy:port
NO_PROXY=localhost,127.0.0.1,nats
```

### 3. 多环境部署

```bash
# 开发环境
helm install my-service ./k8s -f k8s/values-dev.yaml

# 生产环境
helm install my-service ./k8s -f k8s/values-prod.yaml
```

## 故障排查

### 1. Pod 无法启动

```bash
# 查看 Pod 状态
kubectl get pods -n aegis-trader

# 查看 Pod 事件
kubectl describe pod <pod-name> -n aegis-trader

# 查看日志
kubectl logs <pod-name> -n aegis-trader
```

### 2. 镜像加载失败

```bash
# 手动加载镜像
docker save my-service:latest | kind load image-archive - --name aegis-local

# 验证镜像
docker exec -it aegis-local-control-plane crictl images | grep my-service
```

### 3. Helm 部署失败

```bash
# 调试 Helm 模板
helm template my-service ./k8s --debug

# 查看 Helm 历史
helm history my-service -n my-service

# 回滚
helm rollback my-service -n my-service
```

## 生产环境部署

对于生产环境，建议：

1. **使用镜像仓库**
   ```bash
   # 推送到仓库
   docker tag my-service:latest registry.example.com/my-service:v1.0.0
   docker push registry.example.com/my-service:v1.0.0

   # 更新 values.yaml
   image:
     repository: registry.example.com/my-service
     tag: v1.0.0
   ```

2. **使用 GitOps**
   - 将 k8s/ 目录提交到 Git
   - 使用 ArgoCD 或 Flux 自动同步

3. **配置 CI/CD**
   ```yaml
   # .github/workflows/deploy.yml
   name: Deploy to K8s
   on:
     push:
       branches: [main]
   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v2
         - name: Build and push
           run: |
             docker build -t ${{ secrets.REGISTRY }}/my-service:${{ github.sha }} .
             docker push ${{ secrets.REGISTRY }}/my-service:${{ github.sha }}
         - name: Deploy to K8s
           run: |
             helm upgrade --install my-service ./k8s \
               --set image.tag=${{ github.sha }} \
               --namespace production
   ```

## 最佳实践

1. **版本管理**
   - 始终使用版本化的镜像标签
   - 避免在生产环境使用 latest

2. **配置管理**
   - 敏感信息使用 K8s Secrets
   - 环境特定配置使用 values-{env}.yaml

3. **监控和日志**
   - 集成 Prometheus 监控
   - 使用 ELK 或 Loki 收集日志

4. **健康检查**
   - 实现 /health 端点
   - 配置 readiness 和 liveness 探针

## 已知问题和解决方案

### 1. Python types 模块冲突
**问题**：生成的项目包含 `types/` 目录，会与 Python 标准库冲突。
**解决**：已修改模板使用 `app_types/` 避免冲突。

### 2. Dockerfile README.md 缺失
**问题**：构建时提示 README.md 不存在。
**解决**：已更新 Dockerfile 同时复制 pyproject.toml 和 README.md。

### 3. Helm values.yaml 缺少 serviceAccount
**问题**：Helm 部署时提示 serviceAccount 未定义。
**解决**：已在 values.yaml 添加 serviceAccount 配置。

### 4. 代理配置路径问题
**问题**：Makefile 中 .env 路径不正确。
**解决**：智能查找父目录中的 .env 文件（最多 3 层）。

## 验证结果

经过实际测试验证：

- ✅ **项目生成成功**：55 个文件完整生成
- ✅ **Docker 构建成功**：正确加载代理配置
- ✅ **镜像加载成功**：成功加载到 kind 集群 (aegis-local)
- ✅ **Helm 部署成功**：Pod 在 aegis-trader 命名空间正常运行
- ✅ **服务运行正常**：与其他 AegisTrader 服务共同运行
- ✅ **命名空间正确**：部署到 aegis-trader 而非独立命名空间

## 总结

通过 aegis-sdk-dev 生成的项目模板，你可以：

- ✅ **一键部署**：`make deploy-to-kind`
- ✅ **自动处理代理**：智能查找并加载 .env 文件
- ✅ **版本化管理**：自动生成时间戳版本
- ✅ **多环境支持**：dev/staging/prod 配置分离
- ✅ **完整的 DevOps 流程**：从开发到部署
- ✅ **避免常见陷阱**：已修复模块命名冲突等问题

这套模板让你专注于业务逻辑开发，而不是基础设施配置！
