# 使用官方Python 3.12镜像作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt
COPY requirements.txt .

# 安装基础依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 p123client（直接从 GitHub）
RUN pip install --no-cache-dir git+https://github.com/dydydd/p123client.git

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/config /app/logs

# 设置权限
RUN chmod +x start.sh stop.sh 2>/dev/null || true

# 暴露端口
EXPOSE 5245 8096

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5245/api/status || exit 1

# 启动命令
CMD ["python", "app.py"]