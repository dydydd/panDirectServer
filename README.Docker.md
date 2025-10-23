# panDirectServer

🚀 一个强大的 Emby 媒体服务器代理工具，支持 123 网盘直链播放，极致优化播放速度。

[![GitHub](https://img.shields.io/badge/GitHub-panDirectServer-blue?logo=github)](https://github.com/dydydd/panDirectServer)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/dydydd/panDirectServer/blob/main/LICENSE)

---

## ✨ 特性

- 🎯 **智能直链生成**：支持 123 网盘自定义域名 + URL 鉴权，实现极速直链播放
- ⚡ **极致性能优化**：永久路径数据库，二次播放仅需 6ms
- 🔄 **双模式支持**：直链模式（推荐）或代理模式
- 🎬 **Emby 完美集成**：自动 302 重定向，支持路径映射
- 🌐 **Web 管理界面**：美观的现代化 UI，在线配置管理
- 📱 **设备管理**：用户历史追踪，客户端拦截规则
- 🐳 **多架构支持**：`linux/amd64`, `linux/arm64`

---

## 🚀 快速开始

### 使用 Docker Compose（推荐）

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  pandirectserver:
    image: dydydd/pandirectserver:latest
    container_name: pandirectserver
    restart: unless-stopped
    ports:
      - "5245:5245"  # 主服务端口
      - "8096:8096"  # Emby 代理端口
    volumes:
      - ./config:/app/config:rw
      - ./logs:/app/logs:rw
    environment:
      - TZ=Asia/Shanghai
      - LOG_LEVEL=INFO
```

启动服务：

```bash
docker-compose up -d
```

### 使用 Docker Run

```bash
docker run -d \
  --name pandirectserver \
  --restart unless-stopped \
  -p 5245:5245 \
  -p 8096:8096 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  -e TZ=Asia/Shanghai \
  -e LOG_LEVEL=INFO \
  dydydd/pandirectserver:latest
```

---

## 📋 首次配置

### 1. 访问管理界面

启动后访问：**http://your-server-ip:5245**

默认账号：
- 用户名：`admin`
- 密码：`admin123`

⚠️ **首次登录后请立即修改密码！**

### 2. 配置 123 网盘

在管理界面的 "123 网盘设置" 页面填入：

- **Client ID** 和 **Client Secret**：从 [123 网盘开发者平台](https://developers.123pan.com/) 获取
- **下载模式**：选择 `direct`（直链模式，推荐）
- **URL 鉴权**（可选）：
  - 启用 URL 鉴权
  - 填入 `secret_key` 和 `uid`
  - 配置自定义域名

### 3. 配置 Emby

在 "Emby 设置" 页面填入：

- **Emby 服务器地址**：如 `http://your-emby-server:8096`
- **API 密钥**：从 Emby 管理后台获取
- **路径映射**：
  - 启用路径映射
  - **从路径**：Emby 本地路径（如 `/CloudNAS/123云盘`）
  - **到路径**：网盘挂载路径（如 `/123`）

### 4. 保存并重启

点击 "保存配置" 后，点击 "重启服务" 使配置生效。

---

## 🎯 使用场景

### 场景 1：Emby + 123 网盘直链播放

```
Emby 客户端 → panDirectServer (8096) → 123 网盘直链
```

将 Emby 客户端的服务器地址改为：`http://your-server-ip:8096`

**优势**：
- ✅ 播放速度极快（6ms 响应）
- ✅ 不消耗服务器带宽
- ✅ 自动路径映射

### 场景 2：纯 API 服务

```
自定义应用 → panDirectServer API (5245) → 直链
```

使用 API 获取直链：

```bash
curl "http://your-server-ip:5245/api/123/download?path=/123/Movies/movie.mkv"
```

---

## ⚙️ 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TZ` | 时区 | `Asia/Shanghai` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `SERVICE_PORT` | 主服务端口 | `5245` |
| `EMBY_PORT` | Emby 代理端口 | `8096` |

---

## 📁 数据持久化

### 重要目录

```
/app/config/       # 配置文件（必须挂载）
├── config.json    # 主配置文件
├── item_path_db.json  # 路径数据库（性能关键）
└── user_history.json  # 用户历史

/app/logs/         # 日志文件（建议挂载）
└── app.log        # 应用日志
```

### 推荐的卷挂载

```yaml
volumes:
  - ./config:/app/config:rw    # 配置目录（必须）
  - ./logs:/app/logs:rw        # 日志目录（推荐）
```

---

## 🔐 安全建议

### 1. 修改默认密码

首次登录后立即在 "服务设置" 中修改：
- 用户名
- 密码

### 2. 限制访问

使用防火墙或反向代理限制端口访问：

```nginx
# Nginx 示例
location / {
    proxy_pass http://localhost:5245;
    allow 192.168.1.0/24;  # 仅允许内网访问
    deny all;
}
```

### 3. 使用 HTTPS

配置 Nginx/Caddy 反向代理并启用 SSL：

```nginx
server {
    listen 443 ssl http2;
    server_name pandirect.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:5245;
    }
}
```

---

## 📊 性能对比

| 指标 | 直链模式 | 代理模式 |
|------|---------|---------|
| **首次播放** | 59-209ms | 100-300ms |
| **二次播放** | **6ms** ⚡ | 100-200ms |
| **重启后** | **6ms** ⚡ | 100-200ms |
| **服务器带宽** | 不消耗 | 100% 消耗 |
| **推荐度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 🔧 故障排查

### 问题 1：无法访问管理界面

**检查**：
```bash
# 查看容器状态
docker ps | grep pandirectserver

# 查看日志
docker logs pandirectserver

# 检查端口占用
netstat -tulpn | grep 5245
```

### 问题 2：Emby 连接失败

**检查**：
1. Emby 服务器地址是否正确
2. API 密钥是否有效
3. 网络是否互通

**测试连接**：
```bash
curl -H "X-Emby-Token: YOUR_API_KEY" \
  http://your-emby-server:8096/System/Info
```

### 问题 3：123 网盘认证失败

**检查**：
1. Client ID 和 Secret 是否正确
2. 在管理界面点击 "测试连接"
3. 查看日志：`docker logs pandirectserver | grep "123"`

---

## 📚 文档和支持

- **完整文档**：[GitHub README](https://github.com/dydydd/panDirectServer)
- **问题反馈**：[GitHub Issues](https://github.com/dydydd/panDirectServer/issues)
- **讨论交流**：[GitHub Discussions](https://github.com/dydydd/panDirectServer/discussions)

---

## 🏷️ 镜像标签

| 标签 | 说明 | 架构 |
|------|------|------|
| `latest` | 最新稳定版 | amd64, arm64 |
| `main` | 主分支构建 | amd64, arm64 |
| `v1.x.x` | 版本号标签 | amd64, arm64 |

### 拉取指定架构

```bash
# AMD64
docker pull --platform linux/amd64 dydydd/pandirectserver:latest

# ARM64 (树莓派等)
docker pull --platform linux/arm64 dydydd/pandirectserver:latest
```

---

## 🔄 更新

### 更新到最新版本

```bash
# 拉取最新镜像
docker pull dydydd/pandirectserver:latest

# 停止并删除旧容器
docker stop pandirectserver
docker rm pandirectserver

# 启动新容器（使用相同的配置）
docker-compose up -d
# 或
docker run ... (使用相同的参数)
```

### 使用 Docker Compose 更新

```bash
docker-compose pull
docker-compose up -d
```

---

## 🌟 其他镜像源

除了 Docker Hub，还可以从 GitHub Container Registry 拉取：

```bash
# GHCR
docker pull ghcr.io/dydydd/pandirectserver:latest
```

---

## 📝 示例配置

### 完整的 docker-compose.yml

```yaml
version: '3.8'

services:
  pandirectserver:
    image: dydydd/pandirectserver:latest
    container_name: pandirectserver
    hostname: pandirectserver
    restart: unless-stopped
    ports:
      - "5245:5245"
      - "8096:8096"
    volumes:
      - ./config:/app/config:rw
      - ./logs:/app/logs:rw
    environment:
      - TZ=Asia/Shanghai
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5245/api/status"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    networks:
      - pandirectserver-network

networks:
  pandirectserver-network:
    driver: bridge
```

---

## 🎉 快速体验

想快速体验？只需一条命令：

```bash
docker run -d \
  --name pandirectserver \
  -p 5245:5245 -p 8096:8096 \
  dydydd/pandirectserver:latest
```

然后访问：**http://localhost:5245**

---

## ⭐ Star History

如果这个项目对您有帮助，请在 [GitHub](https://github.com/dydydd/panDirectServer) 给个 Star！

---

**构建信息**：
- 基础镜像：`python:3.11-slim`
- 支持架构：`linux/amd64`, `linux/arm64`
- 自动构建：GitHub Actions
- 镜像大小：~200MB

**许可证**：MIT

