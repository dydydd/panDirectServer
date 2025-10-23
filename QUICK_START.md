# 🚀 快速开始指南

## 5分钟部署panDirectServer

### 方式一：Docker部署（最简单）

```bash
# 1. 创建工作目录
mkdir pandirectserver && cd pandirectserver

# 2. 下载docker-compose.yml
wget https://raw.githubusercontent.com/dydydd/embyExternalUrl/main/panDirectServer/docker-compose.yml

# 3. 创建配置目录
mkdir -p config logs

# 4. 启动服务
docker-compose up -d

# 5. 查看日志
docker-compose logs -f

# 6. 访问Web界面
# 打开浏览器: http://localhost:5245
```

### 方式二：使用预构建镜像

修改 `docker-compose.yml`：

```yaml
services:
  pandirectserver:
    image: ghcr.io/dydydd/pandirectserver:latest  # 使用这行
    # build: .  # 注释掉这行
```

然后：
```bash
docker-compose up -d
```

### 方式三：一键运行（测试用）

```bash
docker run -d \
  --name pandirectserver \
  -p 5245:5245 \
  -p 8096:8096 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  ghcr.io/dydydd/pandirectserver:latest
```

## ⚙️ 首次配置

### 1. 访问Web界面

浏览器打开：`http://localhost:5245`

默认登录信息：
- 用户名：`admin`
- 密码：`admin123`

⚠️ **强烈建议立即修改默认密码！**

### 2. 配置123网盘

在Web界面的"123网盘设置"标签：

1. **获取应用凭证**：
   - 访问 [123网盘开发者平台](https://www.123pan.com/developer)
   - 创建应用，获取 `client_id` 和 `client_secret`

2. **填写配置**：
   - Client ID：`你的client_id`
   - Client Secret：`你的client_secret`
   - 挂载路径：`/123`（默认）
   - 下载模式：选择 `direct`（直链，推荐）

3. **配置URL鉴权**（直链模式必需）：
   - 启用URL鉴权：✅
   - Secret Key：你的鉴权密钥
   - UID：你的用户ID
   - 过期时间：`3600`（秒）
   - 自定义域名：`cdn.example.com`（你的CDN域名）

### 3. 配置Emby

在"Emby代理设置"标签：

1. **基本设置**：
   - Emby服务器地址：`http://your-emby-server:8096`
   - API Key：在Emby设置中获取
   - 代理端口：`8096`（默认）

2. **路径映射**（重要！）：
   - 启用路径映射：✅
   - Emby路径前缀：`/mnt/media/123pan`（你的Emby库路径）
   - 云盘路径前缀：`/123`（对应123网盘挂载路径）

   **示例**：
   ```
   Emby路径: /mnt/media/123pan/电影/功夫.mkv
   映射后:   /123/电影/功夫.mkv
   ```

### 4. 保存并重启

点击"保存配置"，然后点击"重启服务"。

## 🎬 配置Emby客户端

修改Emby客户端连接地址：

**原来**：
```
http://your-emby-server:8096
```

**改为**：
```
http://your-pandirectserver:8096
```

或者使用主服务端口（也支持Emby API）：
```
http://your-pandirectserver:5245/emby
```

## ✅ 验证安装

### 1. 检查服务状态

Web界面顶部应显示：
- ✅ 服务运行中
- ✅ Emby已连接
- ✅ 123网盘已连接

### 2. 测试播放

在Emby中播放一个视频，观察日志：

```bash
docker-compose logs -f pandirectserver
```

成功的日志示例：
```
✅ 成功获取 Item 数据: 电影名称
⚡ 数据库命中: 123 → 电影.mkv
✅ 302重定向成功: 电影.mkv
```

### 3. 性能测试

- **首次播放**：50-200ms（需查询Emby API）
- **二次播放**：**6ms** ⚡（数据库命中，极速！）

## 🔧 常见问题

### Q1: 无法连接到123网盘

**检查**：
1. `client_id` 和 `client_secret` 是否正确
2. 网络是否正常
3. 查看日志：`docker-compose logs pandirectserver`

### Q2: 播放失败，无法获取直链

**检查**：
1. 路径映射是否正确配置
2. URL鉴权信息是否正确
3. 自定义域名是否可访问

**调试**：
- 将日志级别改为 `DEBUG`
- 查看详细日志定位问题

### Q3: Docker构建失败

**错误**：`COPY ../p123client /tmp/p123client` 失败

**解决**：确保在项目根目录构建，或修改Dockerfile：
```dockerfile
COPY ../p123client /tmp/p123client
# 改为
COPY ./p123client /tmp/p123client
```

### Q4: 端口冲突

如果5245或8096端口被占用：

修改 `docker-compose.yml`：
```yaml
ports:
  - "5246:5245"  # 改为其他端口
  - "8097:8096"
```

## 📊 性能优化建议

1. **使用直链模式**：比代理模式快95%
2. **启用路径映射**：避免解析STRM文件
3. **调整日志级别**：生产环境使用 `INFO` 或 `WARNING`
4. **SSD存储**：配置文件和数据库使用SSD

## 🎯 进阶配置

### 反向代理（Nginx）

```nginx
server {
    listen 80;
    server_name pandirect.example.com;

    location / {
        proxy_pass http://localhost:5245;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /emby/ {
        proxy_pass http://localhost:8096/emby/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### HTTPS配置

使用Caddy自动获取证书：

```
pandirect.example.com {
    reverse_proxy localhost:5245
}
```

## 📚 下一步

- 阅读 [完整文档](README.md)
- 查看 [性能优化指南](PERFORMANCE.md)
- 了解 [故障排查](TROUBLESHOOTING.md)

---

🎉 恭喜！你已成功部署panDirectServer，享受极速播放体验吧！

