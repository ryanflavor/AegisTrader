# VNPy Docker 部署方案

## 问题
vnpy-ctp 和 vnpy-sopt 在编译时硬编码了临时路径到 .so 文件的 NEEDED 条目中，导致容器运行时找不到库文件。

## 解决方案
使用预编译 wheel + 运行时符号链接：

1. **预编译 wheel 文件**（避免容器内编译）
   - `whl/vnpy_ctp-6.7.7.2-cp313-cp313-linux_x86_64.whl`
   - `whl/vnpy_sopt-3.7.1.0-cp313-cp313-linux_x86_64.whl`
   - `whl/ta_lib-0.6.5-cp313-cp313-manylinux_2_28_x86_64.whl`

2. **K8s ConfigMap 内嵌修复脚本**
   - `k8s/templates/configmap-vnpy-fix.yaml` - 包含内嵌的 Python 脚本
   - 脚本在容器启动时创建符号链接指向正确的库文件位置

3. **快速构建和部署**
   ```bash
   make docker-build-fast     # 使用缓存快速构建
   make deploy-to-kind-fast   # 部署到 K8s
   ```

## 为什么不能用其他方案
- **patchelf**: 无法修改 NEEDED 条目中的硬编码路径
- **ldconfig**: 不能解决 NEEDED 中的绝对路径问题
- **LD_LIBRARY_PATH**: 对硬编码的 NEEDED 路径无效

当前方案虽不优雅但稳定可靠。
