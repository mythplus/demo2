# ============================================
# Mem0 Dashboard 后端 Dockerfile
# 多阶段构建，优化镜像体积
# ============================================

# ---- 阶段 1：安装依赖 ----
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装系统级构建依赖（部分 Python 包需要编译）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- 阶段 2：运行时镜像 ----
FROM python:3.12-slim

WORKDIR /app

# 从 builder 阶段复制已安装的依赖
COPY --from=builder /install /usr/local

# 复制项目源码
COPY server/ ./server/
COPY server.py .
COPY config.yaml.example ./config.yaml.example

# 创建数据目录（Qdrant 本地存储 + SQLite 日志）
RUN mkdir -p /app/qdrant_data /app/data

# 创建非 root 用户运行服务
RUN groupadd -r mem0 && useradd -r -g mem0 -d /app -s /sbin/nologin mem0 \
    && chown -R mem0:mem0 /app
USER mem0

# 环境变量默认值
ENV MEM0_ENV=production \
    MEM0_PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

# 启动命令
CMD ["python", "server.py"]
