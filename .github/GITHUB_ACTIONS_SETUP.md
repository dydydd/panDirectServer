# GitHub Actions 自动构建配置指南

本项目使用GitHub Actions自动构建和发布Docker镜像。

## 🔧 配置步骤

### 1. 配置Docker Hub（可选）

如果要推送到Docker Hub：

1. 访问 GitHub仓库 → Settings → Secrets and variables → Actions
2. 添加以下Secrets：
   - `DOCKER_USERNAME`: 你的Docker Hub用户名
   - `DOCKER_PASSWORD`: 你的Docker Hub密码或访问令牌

### 2. 配置GitHub Container Registry（自动）

GHCR使用GitHub自带的 `GITHUB_TOKEN`，无需额外配置。

### 3. 修改工作流文件

编辑 `.github/workflows/docker-build.yml`：

```yaml
env:
  DOCKER_IMAGE_NAME: pandirectserver  # 修改为你的镜像名称
```

### 4. 触发构建

构建会在以下情况自动触发：

- **推送到主分支**：
  ```bash
  git push origin main
  ```
  生成镜像：`pandirectserver:latest`

- **创建版本标签**：
  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```
  生成镜像：
  - `pandirectserver:v1.0.0`
  - `pandirectserver:1.0`
  - `pandirectserver:1`
  - `pandirectserver:latest`

- **手动触发**：
  访问 Actions → Build and Push Docker Image → Run workflow

## 📦 使用构建的镜像

### 从Docker Hub拉取

```bash
docker pull dydydd/pandirectserver:latest
```

### 从GHCR拉取

```bash
docker pull ghcr.io/dydydd/pandirectserver:latest
```

### 在docker-compose.yml中使用

```yaml
services:
  pandirectserver:
    image: ghcr.io/dydydd/pandirectserver:latest
    # 或者
    # image: dydydd/pandirectserver:latest
```

## 🏗️ 构建信息

- **支持架构**：`linux/amd64`, `linux/arm64`
- **构建时间**：约5-10分钟
- **镜像大小**：约300-400MB

## 🔍 查看构建状态

访问：https://github.com/dydydd/embyExternalUrl/actions

## ❓ 常见问题

### Q: 构建失败，提示权限错误

A: 确保在仓库Settings中启用了Actions权限：
- Settings → Actions → General
- 勾选 "Read and write permissions"

### Q: 无法推送到GHCR

A: 确保GHCR包可见性设置正确：
- 访问 Packages → pandirectserver → Package settings
- 修改可见性为 Public

### Q: 如何只构建特定架构？

A: 修改工作流文件中的 `DOCKER_PLATFORMS`：
```yaml
env:
  DOCKER_PLATFORMS: linux/amd64  # 只构建amd64
```

## 🎯 最佳实践

1. **使用语义化版本**：
   ```bash
   git tag v1.2.3
   ```

2. **主分支保持稳定**：
   - 在开发分支开发
   - 测试通过后合并到main

3. **定期清理旧镜像**：
   - 在GHCR Packages页面删除旧版本

## 📝 工作流说明

```yaml
name: Build and Push Docker Image

# 触发条件
on:
  push:
    branches: [main, master]
    tags: ['v*']
  pull_request:
    branches: [main, master]
  workflow_dispatch:  # 手动触发

# 构建步骤
jobs:
  build:
    - Checkout代码
    - 设置QEMU（多架构支持）
    - 设置Docker Buildx
    - 登录Docker Hub
    - 登录GHCR
    - 提取元数据（标签）
    - 构建并推送镜像
```

## 🚀 手动触发构建

1. 访问仓库的 Actions 页面
2. 选择 "Build and Push Docker Image"
3. 点击 "Run workflow"
4. 选择分支，点击 "Run workflow"

---

配置完成后，每次推送代码或创建标签，都会自动构建并发布Docker镜像！

