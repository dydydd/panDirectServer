# Git 子模块配置说明

本项目使用 Git 子模块来管理 `p123client` 依赖。

## 📋 项目结构

```
panDirectServer/                 # 主仓库
├── p123client/                  # Git 子模块（独立仓库）
├── models/
├── services/
├── utils/
├── templates/
├── requirements.txt
├── Dockerfile
└── ...
```

## 🔗 子模块信息

- **子模块名称**: p123client
- **子模块仓库**: https://github.com/dydydd/p123client.git
- **位置**: `./p123client/`

## 🚀 初次克隆（推荐）

### 方法1：克隆时包含子模块（推荐）

```bash
# 一次性克隆主仓库和所有子模块
git clone --recursive https://github.com/dydydd/panDirectServer.git
cd panDirectServer
```

### 方法2：先克隆主仓库，再初始化子模块

```bash
# 克隆主仓库
git clone https://github.com/dydydd/panDirectServer.git
cd panDirectServer

# 初始化并拉取子模块
git submodule update --init --recursive
```

## 📦 子模块管理命令

### 初始化子模块

```bash
# 初始化所有子模块
git submodule init

# 拉取子模块内容
git submodule update
```

### 更新子模块到最新版本

```bash
# 更新所有子模块到其远程仓库的最新提交
git submodule update --remote

# 或者进入子模块目录手动更新
cd p123client
git pull origin main
cd ..
```

### 查看子模块状态

```bash
# 查看子模块状态
git submodule status

# 查看子模块配置
git config --file .gitmodules --get-regexp path
```

## 🏗️ 开发者指南

### 修改子模块代码

```bash
# 1. 进入子模块目录
cd p123client

# 2. 切换到开发分支
git checkout main

# 3. 进行修改...

# 4. 提交子模块的更改
git add .
git commit -m "Update p123client"
git push origin main

# 5. 返回主仓库，更新子模块引用
cd ..
git add p123client
git commit -m "Update p123client submodule"
git push
```

### 添加新的子模块（维护者）

```bash
# 添加子模块
git submodule add https://github.com/dydydd/p123client.git p123client

# 提交子模块配置
git add .gitmodules p123client
git commit -m "Add p123client as submodule"
git push
```

## 🐳 Docker 构建

Dockerfile 已配置为自动处理子模块：

```dockerfile
# 复制整个项目（包括子模块）
COPY . .

# 初始化Git子模块（如果还没初始化）
RUN if [ -f .gitmodules ]; then \
        git config --global --add safe.directory /app && \
        git submodule update --init --recursive || true; \
    fi

# 安装p123client子模块
RUN if [ -d "p123client" ]; then \
        pip install --no-cache-dir ./p123client; \
    else \
        echo "Warning: p123client submodule not found"; \
    fi
```

## 🔍 常见问题

### Q1: 克隆后 p123client 目录为空？

**原因**: 没有初始化子模块。

**解决**:
```bash
git submodule update --init --recursive
```

### Q2: 子模块提示 "detached HEAD"？

**原因**: 子模块默认处于分离头指针状态，这是正常的。

**解决**: 如果需要修改子模块代码：
```bash
cd p123client
git checkout main
```

### Q3: 拉取主仓库更新后，子模块没有更新？

**原因**: `git pull` 不会自动更新子模块。

**解决**:
```bash
# 拉取主仓库更新
git pull

# 更新子模块
git submodule update --recursive
```

或者使用：
```bash
# 一次性拉取主仓库和子模块
git pull --recurse-submodules
```

### Q4: GitHub Actions 中如何处理子模块？

在 `.github/workflows/docker-build.yml` 中已配置：

```yaml
- name: Checkout code
  uses: actions/checkout@v4
  with:
    submodules: recursive  # 自动拉取子模块
```

## 📝 .gitmodules 配置

文件位置：`./gitmodules`

```ini
[submodule "p123client"]
    path = p123client
    url = https://github.com/dydydd/p123client.git
```

## ⚠️ 重要提示

1. **不要直接修改子模块目录下的代码**，除非你知道自己在做什么。
2. **主仓库只存储子模块的引用**（commit hash），不存储子模块的实际代码。
3. **Docker 构建时**会自动处理子模块，无需手动操作。
4. **CI/CD 流程**已配置为自动拉取子模块。

## 🔗 相关链接

- [主仓库](https://github.com/dydydd/panDirectServer)
- [p123client 子模块](https://github.com/dydydd/p123client)
- [Git 子模块官方文档](https://git-scm.com/book/en/v2/Git-Tools-Submodules)

---

如有问题，请访问 [Issues](https://github.com/dydydd/panDirectServer/issues)

