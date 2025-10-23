# ✅ 提交前检查清单

在提交代码到GitHub之前，请确保完成以下检查：

## 🔐 安全检查

- [x] 已清理 `config/config.json` 中的所有敏感信息
- [x] 已删除所有包含真实凭证的文件
- [x] 已验证 `.gitignore` 包含所有敏感文件
- [x] 已删除所有token、cookies等认证文件
- [ ] 检查代码中是否有硬编码的密码/密钥
- [ ] 检查日志输出是否包含敏感信息

## 🧹 清理检查

- [x] 已删除所有测试文件（`test_*.py`）
- [x] 已删除临时文件（`.7z`, `.zip`等）
- [x] 已删除缓存文件
- [x] 已删除用户数据文件
- [ ] 清理 `__pycache__` 目录

## 📝 文档检查

- [x] `README.md` 已更新
- [x] `CHANGELOG.md` 已更新
- [x] `QUICK_START.md` 已创建
- [ ] API文档已更新（如有变更）
- [ ] 配置示例已更新

## 🐳 Docker检查

- [x] `Dockerfile` 已优化
- [x] `docker-compose.yml` 已更新
- [x] `.dockerignore` 已创建（如需要）
- [ ] 本地测试Docker构建成功
  ```bash
  docker build -t pandirectserver:test .
  ```

## 🔧 GitHub Actions检查

- [x] `.github/workflows/docker-build.yml` 已创建
- [x] 工作流配置正确
- [ ] 已在GitHub仓库设置Secrets（如需要）
  - `DOCKER_USERNAME`
  - `DOCKER_PASSWORD`

## 🎯 功能检查

- [ ] 所有功能正常工作
- [ ] 配置文件格式正确
- [ ] Web界面可以正常访问
- [ ] 直链模式测试通过
- [ ] 代理模式测试通过（如使用）

## 📦 依赖检查

- [x] `requirements.txt` 已更新
- [ ] 所有依赖可以正常安装
  ```bash
  pip install -r requirements.txt
  ```

## 📋 Git检查

- [ ] 查看待提交文件列表
  ```bash
  git status
  ```
- [ ] 检查差异
  ```bash
  git diff
  ```
- [ ] 确认没有意外文件
- [ ] 提交信息清晰明确

## 🚀 提交步骤

完成以上检查后，执行以下命令：

```bash
# 1. 查看状态
git status

# 2. 添加文件
git add .

# 3. 查看待提交内容
git diff --staged

# 4. 提交
git commit -m "feat: 初始版本 - 支持123网盘直链播放"

# 5. 推送到GitHub
git push origin main

# 6. 创建版本标签（可选）
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## ⚠️ 最后确认

提交前，再次确认：

1. ✅ 配置文件中**没有任何**真实的：
   - API Key
   - Client ID/Secret
   - 用户名/密码
   - 域名（除非是示例）
   - IP地址（除非是示例）

2. ✅ 所有示例配置使用占位符：
   - `YOUR_CLIENT_ID`
   - `YOUR_SECRET_KEY`
   - `your-domain.com`
   - `localhost`

3. ✅ `.gitignore` 正确配置，敏感文件不会被提交

## 🎉 提交成功后

1. 访问GitHub仓库查看Actions运行状态
2. 等待Docker镜像构建完成
3. 测试拉取构建的镜像：
   ```bash
   docker pull ghcr.io/dydydd/pandirectserver:latest
   ```
4. 更新README中的镜像链接

---

**重要提醒**：一旦敏感信息提交到GitHub，即使删除提交，历史记录中仍可能存在。请务必在提交前完成所有检查！

