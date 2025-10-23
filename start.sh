#!/bin/bash

# PanDirect Server 启动脚本

echo "========================================="
echo "  PanDirect Server - 网盘直链服务"
echo "========================================="
echo ""

# 检查是否安装了 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    echo "访问 https://docs.docker.com/get-docker/ 获取安装指南"
    exit 1
fi

# 检查是否安装了 docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose 未安装，请先安装 docker-compose"
    echo "访问 https://docs.docker.com/compose/install/ 获取安装指南"
    exit 1
fi

# 创建配置目录
if [ ! -d "config" ]; then
    echo "📁 创建配置目录..."
    mkdir -p config
fi

# 复制示例配置文件
if [ ! -f "config/config.json" ]; then
    if [ -f "config/config.json.example" ]; then
        echo "📄 复制默认配置文件..."
        cp config/config.json.example config/config.json
    fi
fi

# 创建 .env 文件
if [ ! -f ".env" ]; then
    echo "🔐 创建环境变量文件..."
    cat > .env << EOF
# Flask 配置
SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "your-secret-key-$(date +%s)")
DEBUG=false

# Docker 配置
TZ=Asia/Shanghai
EOF
    echo "✅ 已生成随机 SECRET_KEY"
fi

# 构建镜像
echo ""
echo "🐳 构建 Docker 镜像..."
docker-compose build

# 启动服务
echo ""
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo ""
echo "⏳ 等待服务启动..."
sleep 3

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "✅ PanDirect Server 启动成功！"
    echo ""
    echo "🌐 管理界面：http://localhost:5245"
    echo "📡 API 地址：http://localhost:5245/api"
    echo ""
    echo "默认管理员账号："
    echo "  用户名：admin"
    echo "  密码：admin123"
    echo ""
    echo "💡 提示："
    echo "  - 请访问管理界面配置网盘账号"
    echo "  - 配置文件位置：./config/config.json"
    echo "  - 查看日志：docker-compose logs -f"
    echo "  - 停止服务：docker-compose down"
    echo "  - 重启服务：docker-compose restart"
else
    echo ""
    echo "❌ 服务启动失败，请检查日志："
    echo "docker-compose logs"
    exit 1
fi

echo ""
echo "========================================="
