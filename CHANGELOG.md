# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 🚀 永久路径数据库，极致优化播放速度（二次播放仅6ms）
- ⚡ 智能直链生成，支持123网盘自定义域名+URL鉴权
- 🎯 双模式支持：直链模式（推荐）和代理模式
- 🌐 Web管理界面，美观的现代化UI
- 📊 实时状态监控和在线配置管理
- 🔄 Emby API反向代理，自动302重定向
- 🗺️ 路径映射功能（Emby本地路径 → 云盘路径）
- 📝 可配置日志级别（DEBUG/INFO/WARNING/ERROR）
- 🐳 Docker支持，一键部署
- 🔧 GitHub Actions自动构建多架构Docker镜像

### Changed
- ♻️ 移除115网盘支持，专注123网盘优化
- 🎨 优化前端UI，提升用户体验
- ⚡ 大幅减少日志输出，提升性能
- 🔒 改进URL编码处理，修复代理模式播放问题

### Fixed
- 🐛 修复代理模式URL参数截断问题
- 🐛 修复配置文件敏感信息掩码处理
- 🐛 修复路径映射配置未生效问题
- 🐛 修复缓存机制导致的播放延迟

### Security
- 🔐 清理敏感配置信息，确保GitHub安全
- 🛡️ 添加.gitignore，防止敏感文件泄露

## [1.0.0] - YYYY-MM-DD

### Added
- 🎉 Initial release
- ✨ 123网盘直链播放支持
- 🎬 Emby媒体服务器代理
- 📦 Docker部署支持
- 📖 完整文档

---

## 版本说明

### 语义化版本号

- **MAJOR（主版本）**：不兼容的API变更
- **MINOR（次版本）**：向后兼容的功能新增
- **PATCH（补丁）**：向后兼容的问题修正

### 变更类型

- `Added` - 新增功能
- `Changed` - 功能变更
- `Deprecated` - 即将废弃的功能
- `Removed` - 已删除的功能
- `Fixed` - Bug修复
- `Security` - 安全相关

[Unreleased]: https://github.com/dydydd/embyExternalUrl/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/dydydd/embyExternalUrl/releases/tag/v1.0.0

