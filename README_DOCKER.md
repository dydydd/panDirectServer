# PanDirectServer Docker 部署

这是一个用于Emby媒体服务器的云盘直链代理服务，支持115网盘和123云盘。

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone <repository-url>
cd panDirectServer
```

### 2. 启动服务
```bash
# 使用docker-compose启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 3. 配置服务
访问管理界面进行配置：
- 管理界面: http://localhost:5245
- 默认用户名: admin
- 默认密码: admin123

### 4. 访问服务
- 管理界面: http://localhost:5245
- Emby代理: http://localhost:8096

## 📋 配置说明

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

## 🔧 功能特性

- ✅ Emby反向代理
- ✅ 115网盘支持
- ✅ 123云盘支持
- ✅ STRM文件解析
- ✅ 直链代理下载
- ✅ 客户端拦截管理
- ✅ Web管理界面
- ✅ Alist API兼容

## 📁 目录结构

```
panDirectServer/
├── Dockerfile              # Docker镜像构建文件
├── docker-compose.yml      # Docker Compose配置
├── .dockerignore          # Docker忽略文件
├── .gitignore             # Git忽略文件
├── test_docker.sh         # Docker测试脚本
├── DOCKER_GUIDE.md        # Docker部署指南
├── config/
│   ├── config.json.template  # 配置模板
│   └── config.json.example   # 配置示例
├── app.py                 # 主应用文件
├── requirements.txt       # Python依赖
└── start.sh              # 启动脚本
```

## 🛠️ 开发调试

### 本地开发
```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

### Docker调试
```bash
# 进入容器
docker-compose exec pandirectserver bash

# 查看日志
docker-compose logs -f pandirectserver

# 重启服务
docker-compose restart pandirectserver
```

## 🔒 安全注意事项

1. **修改默认密码**: 务必修改管理界面的默认密码
2. **修改API令牌**: 务必修改API访问令牌
3. **网络安全**: 生产环境建议使用HTTPS和反向代理

## 📊 监控和日志

### 健康检查
服务提供健康检查端点：
```bash
curl http://localhost:5245/api/status
```

### 日志查看
```bash
# 实时日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f pandirectserver
```

## 🚨 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 检查端口占用
   netstat -tulpn | grep :5245
   netstat -tulpn | grep :8096
   ```

2. **权限问题**
   ```bash
   # 修复权限
   chmod +x start.sh stop.sh
   ```

3. **配置错误**
   ```bash
   # 检查配置
   docker-compose exec pandirectserver cat /app/config/config.json
   ```

### 重置服务
```bash
# 停止并删除容器
docker-compose down

# 删除数据卷
docker-compose down -v

# 重新构建
docker-compose build --no-cache
docker-compose up -d
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

## 📝 更新日志

- v1.0.0: 初始Docker支持
- 支持前端配置管理
- 支持敏感信息保护
- 支持健康检查

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目采用MIT许可证。