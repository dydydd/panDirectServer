# panDirectServer

🚀 一个强大的Emby媒体服务器代理工具，支持123网盘直链播放，极致优化播放速度。

[![Docker Build](https://github.com/dydydd/panDirectServer/actions/workflows/docker-build.yml/badge.svg)](https://github.com/dydydd/panDirectServer/actions/workflows/docker-build.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)

## ✨ 特性

- 🎯 **智能直链生成**：支持123网盘自定义域名 + URL鉴权，实现极速直链播放
- ⚡ **极致性能优化**：
  - 永久路径数据库，二次播放仅需6ms
  - 智能缓存机制，避免重复API查询
  - 可配置日志级别，减少I/O开销
- 🔄 **双模式支持**：
  - **直链模式**（推荐）：域名+路径+鉴权，极速播放
  - **代理模式**：服务器转发流量，适用于无自定义域名场景
- 🎬 **Emby完美集成**：
  - 反向代理Emby API
  - 自动302重定向到直链
  - 支持路径映射（本地路径 → 云盘路径）
- 🌐 **Web管理界面**：
  - 美观的现代化UI
  - 实时状态监控
  - 在线配置管理
- 🐳 **Docker部署**：开箱即用，自动构建多架构镜像

## 📋 快速开始

### Docker部署（推荐）

#### 使用预构建镜像

```bash
# 1. 下载docker-compose.yml
wget https://raw.githubusercontent.com/dydydd/panDirectServer/main/docker-compose.yml

# 2. 创建配置目录
mkdir -p config logs

# 3. 修改docker-compose.yml，使用预构建镜像
# 取消注释: image: ghcr.io/dydydd/pandirectserver:latest
# 注释掉: build 部分

# 4. 启动服务
docker-compose up -d

# 5. 访问管理界面
# 主服务: http://localhost:5245
# Emby代理: http://localhost:8096
```

#### 本地构建

```bash
# 克隆仓库（包含子模块）
git clone --recursive https://github.com/dydydd/panDirectServer.git
cd panDirectServer

# 启动服务
docker-compose up -d
```

### 手动部署

```bash
# 1. 克隆仓库（包含子模块）
git clone --recursive https://github.com/dydydd/panDirectServer.git
cd panDirectServer

# 如果已经克隆但忘记了 --recursive，可以执行：
git submodule update --init --recursive

# 2. 安装p123client依赖（子模块）
cd p123client
pip install -e .

# 3. 安装panDirectServer依赖
cd ..
pip install -r requirements.txt

# 4. 启动服务
python app.py
```

## ⚙️ 配置说明

### 配置文件

配置文件位于 `config/config.json`，首次启动会自动创建。

```json
{
  "123": {
    "enable": true,
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "mount_path": "/123",
    "download_mode": "direct",
    "url_auth": {
      "enable": true,
      "secret_key": "YOUR_SECRET_KEY",
      "uid": "YOUR_UID",
      "expire_time": 3600,
      "custom_domains": ["your-domain.com"]
    }
  },
  "emby": {
    "enable": true,
    "server": "http://your-emby-server:8096",
    "api_key": "YOUR_EMBY_API_KEY",
    "port": 8096,
    "path_mapping": {
      "enable": true,
      "from": "/your/emby/path",
      "to": "/123"
    }
  },
  "service": {
    "port": 5245,
    "external_url": "http://your-server.com:5245",
    "log_level": "INFO"
  }
}
```

### 配置项详解

#### 123网盘配置

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `client_id` | 123网盘应用ID | `"xxx"` |
| `client_secret` | 123网盘应用密钥 | `"xxx"` |
| `download_mode` | 下载模式：`direct`（直链）或 `proxy`（代理） | `"direct"` |
| `url_auth.enable` | 是否启用URL鉴权 | `true` |
| `url_auth.secret_key` | URL鉴权密钥 | `"xxx"` |
| `url_auth.uid` | 用户ID | `"123456"` |
| `url_auth.custom_domains` | 自定义域名列表 | `["cdn.example.com"]` |

#### Emby配置

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `server` | Emby服务器地址 | `"http://localhost:8096"` |
| `api_key` | Emby API密钥 | `"xxx"` |
| `port` | Emby代理监听端口 | `8096` |
| `path_mapping.enable` | 是否启用路径映射 | `true` |
| `path_mapping.from` | Emby本地路径前缀 | `"/mnt/media"` |
| `path_mapping.to` | 云盘路径前缀 | `"/123"` |

#### 服务配置

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `port` | 主服务端口 | `5245` |
| `external_url` | 外部访问地址（代理模式必需） | `"http://server.com:5245"` |
| `log_level` | 日志级别：`DEBUG`, `INFO`, `WARNING`, `ERROR` | `"INFO"` |

## 📖 使用指南

### 直链模式设置（推荐）

1. **配置123网盘URL鉴权**：
   - 登录123网盘开发者平台
   - 获取 `secret_key` 和 `uid`
   - 配置自定义CDN域名

2. **修改配置**：
   ```json
   {
     "123": {
       "download_mode": "direct",
       "url_auth": {
         "enable": true,
         "secret_key": "YOUR_SECRET",
         "uid": "YOUR_UID",
         "custom_domains": ["cdn.example.com"]
       }
     }
   }
   ```

3. **配置Emby路径映射**：
   ```json
   {
     "emby": {
       "path_mapping": {
         "enable": true,
         "from": "/CloudNAS/123云盘",
         "to": "/123"
       }
     }
   }
   ```

4. **重启服务**，享受极速播放！

### 代理模式设置

如果没有自定义域名，可使用代理模式：

```json
{
  "123": {
    "download_mode": "proxy"
  },
  "service": {
    "external_url": "http://your-server.com:5245"
  }
}
```

⚠️ **注意**：代理模式会消耗服务器带宽，速度较慢。

## 🎯 性能对比

| 指标 | 直链模式 | 代理模式 |
|------|---------|---------|
| **首次播放** | 59-209ms | 100-300ms |
| **二次播放** | **6ms** ⚡ | 100-200ms |
| **重启后** | **6ms** ⚡ | 100-200ms |
| **服务器带宽** | 不消耗 | 100%消耗 |
| **推荐度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

## 🔧 高级功能

### 永久路径数据库

系统会自动记录 `item_id → 文件路径` 映射到 `config/item_path_db.json`：

- ✅ 重启不丢失
- ✅ 自动增长
- ✅ 二次播放完全跳过Emby API查询

### 智能日志控制

```json
{
  "service": {
    "log_level": "INFO"  // DEBUG, INFO, WARNING, ERROR
  }
}
```

- **DEBUG**：最详细，包含所有调试信息
- **INFO**：正常，记录关键操作
- **WARNING**：仅警告和错误
- **ERROR**：仅错误

### Web管理界面

访问 `http://localhost:5245` 可以：

- 📊 查看实时状态
- ⚙️ 在线修改配置
- 🔄 重启服务
- 🧪 测试连接

## 📊 API接口

### 状态查询

```bash
GET http://localhost:5245/api/status
```

响应：
```json
{
  "code": 200,
  "data": {
    "service": {
      "status": "running",
      "port": 5245
    },
    "emby": {
      "status": "running",
      "port": 8096,
      "server": "http://localhost:8096"
    },
    "123": {
      "status": "connected"
    }
  }
}
```

### 配置管理

```bash
# 获取配置
GET http://localhost:5245/api/config

# 更新配置
POST http://localhost:5245/api/config
Content-Type: application/json

{
  "service": {...},
  "emby": {...},
  "123": {...}
}
```

## 🐳 Docker构建

### 本地构建

```bash
docker build -t pandirectserver:latest .
```

### 多架构构建

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t pandirectserver:latest \
  --push .
```

### GitHub Actions自动构建

提交代码到GitHub后，会自动触发构建流程：

- 推送到 `main` 或 `master` 分支
- 创建标签（如 `v1.0.0`）
- 手动触发工作流

镜像会推送到：
- Docker Hub: `dydydd/pandirectserver`
- GHCR: `ghcr.io/dydydd/pandirectserver`

## 🔐 安全建议

1. **修改默认密码**：
   ```json
   {
     "service": {
       "username": "your_username",
       "password": "your_strong_password"
     }
   }
   ```

2. **使用HTTPS**：
   - 配置反向代理（Nginx/Caddy）
   - 启用SSL证书

3. **限制访问**：
   - 使用防火墙限制端口访问
   - 配置IP白名单

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📝 许可证

本项目采用 MIT 许可证，详见 [LICENSE](../LICENSE) 文件。

## 🙏 致谢

- [p123client](../p123client) - 123网盘Python客户端
- [Flask](https://flask.palletsprojects.com/) - Web框架
- [Emby](https://emby.media/) - 媒体服务器

## 📮 联系方式

- GitHub Issues: [提交问题](https://github.com/dydydd/panDirectServer/issues)
- Discussions: [讨论区](https://github.com/dydydd/panDirectServer/discussions)

---

⭐ 如果这个项目对您有帮助，请给个Star！
