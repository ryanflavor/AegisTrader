# Staging Environment Quick Start Guide

## Option 1: Local Staging (推荐用于开发)

最简单的方式是在本地运行staging环境：

```bash
# 一键部署本地staging
make deploy-local-staging

# 查看状态
make staging-status

# 清理环境
make staging-clean
```

## Option 2: GitHub Actions Staging

### 1. 设置 GitHub Secret

运行自动配置脚本：
```bash
./scripts/setup-github-staging-secret.sh
```

或手动设置：
1. 获取kubeconfig的base64编码：
   ```bash
   cat ~/.kube/config | base64 -w 0
   ```
2. 在GitHub仓库设置中添加secret：
   - 名称：`KUBE_CONFIG`
   - 值：上面的base64输出

### 2. 推送代码触发部署

```bash
git push origin main
```

CI/CD将自动：
- 运行测试
- 构建Docker镜像
- 部署到staging环境

## 访问服务

部署完成后，通过端口转发访问：

```bash
# API服务
kubectl port-forward -n aegis-staging svc/monitor-api 8100:8100

# UI服务
kubectl port-forward -n aegis-staging svc/monitor-ui 3100:3100

# NATS
kubectl port-forward -n aegis-staging svc/nats 4222:4222
```

然后访问：
- API: http://localhost:8100/health
- UI: http://localhost:3100
- NATS: localhost:4222

## 故障排除

1. **检查部署状态**
   ```bash
   kubectl get all -n aegis-staging
   ```

2. **查看日志**
   ```bash
   kubectl logs -n aegis-staging -l app=monitor-api
   ```

3. **重新部署**
   ```bash
   make staging-clean
   make deploy-local-staging
   ```

## 详细文档

- 完整设置指南：[docs/setup-staging-environment.md](docs/setup-staging-environment.md)
- CI/CD配置：[.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml)
