# 下载模式配置说明

## 下载模式开关

在 `config.json` 的 `123` 配置中添加了 `download_mode` 参数，用于控制文件下载方式：

```json
{
  "123": {
    "download_mode": "direct"  // 或 "proxy"
  }
}
```

## 模式说明

### 🔗 直链模式 (`"direct"`)
- **默认模式**，优先使用自定义域名 + 路径直出
- 需要配置 `url_auth` 相关参数
- 如果直链失败，会自动降级到代理模式
- **优点**：速度快，直接访问
- **缺点**：需要配置自定义域名和URL鉴权

### 🔒 代理模式 (`"proxy"`)
- 强制使用代理下载方式
- 通过123网盘API获取下载链接，然后通过内部代理服务处理
- 不需要自定义域名配置
- **优点**：兼容性好，无需额外配置
- **缺点**：速度较慢，消耗服务器带宽

## 配置示例

### 直链模式配置
```json
{
  "123": {
    "enable": true,
    "download_mode": "direct",
    "url_auth": {
      "enable": true,
      "secret_key": "your_secret_key",
      "uid": "your_uid",
      "expire_time": 3600,
      "custom_domains": ["your-domain.com"]
    }
  }
}
```

### 代理模式配置
```json
{
  "123": {
    "enable": true,
    "download_mode": "proxy",
    "token": "your_token",
    "client_id": "your_client_id",
    "client_secret": "your_client_secret"
  }
}
```

## 切换方式

1. **修改配置文件**：编辑 `config/config.json` 中的 `download_mode` 值
2. **重启服务**：重启 `panDirectServer` 使配置生效
3. **验证模式**：查看日志中的 `📥 下载模式: xxx` 信息

## 日志标识

- `🔗 使用直链模式` - 当前使用直链模式
- `🔒 使用代理下载模式` - 当前使用代理模式
- `⚠️ 域名直出失败，降级到代理下载` - 直链模式失败，自动降级

## 注意事项

- 切换模式后需要重启服务才能生效
- 不同模式使用不同的缓存键，避免缓存冲突
- 代理模式会消耗服务器带宽，建议在直链模式不可用时使用
