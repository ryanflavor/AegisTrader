# Debug Log - AegisTrader Project

## Story 0.1: Containerize Applications

### Issue: npm install slow/hanging in Docker build

#### Root Cause
- Host proxy at `http://192.168.10.23:10809` not accessible from Docker build context
- Container network isolation prevents access to host's localhost/192.168.x.x addresses
- Docker daemon had proxy configured but build process requires explicit build args

#### Solution
Use Docker build arguments to pass proxy settings:
```bash
docker build \
  --build-arg HTTP_PROXY=http://192.168.10.23:10809 \
  --build-arg HTTPS_PROXY=http://192.168.10.23:10809 \
  --build-arg NO_PROXY=localhost,127.0.0.1 \
  -f apps/monitor-ui/Dockerfile \
  -t aegistrader/monitor-ui:latest .
```

#### Key Changes
1. Updated Dockerfile to accept and use ARG directives for proxy
2. Set proxy env vars during build, cleared them for runtime
3. npm install completed in ~30s vs timing out

#### Result
Both images built successfully:
- aegistrader/monitor-api:latest (543MB) - Port 8100
- aegistrader/monitor-ui:latest (838MB) - Port 3100

---

## Story 0.2: Kubernetes Deployment with KIND

### Issue: KIND 部署时 ErrImagePull 错误

#### 问题根因
**containerd 命名空间不匹配** - K8s 使用 `k8s.io` 命名空间，而默认导入到 default 命名空间

#### 调试关键命令
```bash
# 错误：导入到默认命名空间
docker save image:tag | docker exec -i kind-control-plane ctr images import -

# 正确：导入到 k8s.io 命名空间
docker save image:tag | docker exec -i kind-control-plane ctr -n k8s.io images import -

# 验证：查看 K8s 能看到的镜像
docker exec kind-control-plane crictl images
```

#### 最终解决方案
```makefile
# Makefile 中正确的镜像加载命令
@docker save $(IMAGE):$(VERSION) | docker exec -i $(KIND_CONTROL_PLANE) ctr -n k8s.io images import -
```

#### 核心教训（3条）
1. **KIND 使用 k8s.io 命名空间**：必须用 `ctr -n k8s.io images import`
2. **避免 latest 标签**：使用具体版本号（如 v1.0.0）
3. **crictl vs ctr**：crictl 显示 K8s 能看到的镜像，ctr 需指定命名空间

