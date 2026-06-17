FROM python:3.12-alpine

WORKDIR /app

# 安装 uv 和必要的构建工具
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# 安装运行时依赖和构建依赖
RUN apk add --no-cache curl gcc musl-dev libffi-dev && \
    rm -rf /var/cache/apk/*

# 先复制依赖文件，利用 Docker 缓存层
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

# 复制应用代码
COPY app/ ./app/

# 创建数据目录（用于 SQLite 会话存储）
RUN mkdir -p data

# 清理构建依赖，进一步减小镜像体积
RUN apk del gcc musl-dev libffi-dev

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
