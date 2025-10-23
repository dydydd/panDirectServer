#!/bin/bash

# PanDirect Server 停止脚本

echo "========================================="
echo "  PanDirect Server - 停止服务"
echo "========================================="
echo ""

# 停止服务
echo "🛑 停止服务..."
docker-compose down

echo ""
echo "✅ 服务已停止"
echo ""
echo "💡 提示："
echo "  - 配置文件已保留：./config/"
echo "  - 重新启动：./start.sh 或 docker-compose up -d"
echo ""
echo "========================================="
