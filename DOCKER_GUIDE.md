# Docker 部署指南

## 快速开始

### 1. 启动服务

直接使用 docker-compose 启动：
```bash
docker-compose up -d
```

### 2. 配置服务

启动后访问管理界面进行配置：
- 管理界面: http://localhost:5245
- 默认用户名: admin
- 默认密码: admin123

### 3. 查看日志

```bash
docker-compose logs -f
```

### 4. 停止服务

```bash
docker-compose down
```

## 端口说明

- `5245`: 主服务端口 (Web管理界面 + Alist API)
- `8096`: Emby反向代理端口

## 数据持久化

以下目录会被持久化：
- `./config`: 配置文件目录
- `./logs`: 日志文件目录

## 配置说明

### 默认配置

服务启动时会使用默认配置，包含：
- 管理界面用户名: admin
- 管理界面密码: admin123
- API访问令牌: emby-proxy-token
- 123云盘客户端ID和密钥（已内置）

### 前端配置

所有配置都可以通过Web管理界面进行修改：
1. 访问 http://localhost:5245
2. 使用默认账号登录
3. 在配置页面填入你的实际配置

### 主要配置项

- **Emby服务器**: 你的Emby服务器地址
- **Emby API密钥**: Emby的API密钥
- **123云盘Token**: 123云盘的访问令牌
- **123云盘密码**: 123云盘的登录密码
- **115网盘Cookies**: 115网盘的Cookies（如果使用115网盘）

## 安全注意事项

1. **修改默认密码**: 首次使用请务必修改管理界面的默认密码
2. **修改API令牌**: 建议修改API访问令牌
3. **网络安全**: 在生产环境中，建议使用反向代理和HTTPS

## 故障排除

### 查看容器状态
```bash
docker-compose ps
```

### 进入容器调试
```bash
docker-compose exec pandirectserver bash
```

### 重新构建镜像
```bash
docker-compose build --no-cache
docker-compose up -d
```

### 清理数据
```bash
docker-compose down -v
docker system prune -f
```

### 重置配置
```bash
# 停止服务
docker-compose down

# 删除配置文件
rm -rf config/config.json

# 重新启动（会使用默认配置）
docker-compose up -d
```
