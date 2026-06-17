#!/bin/bash
# Dangbei2API 启动脚本

set -e

echo "🚀 Dangbei2API 启动中..."

# 检查环境
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，复制示例配置..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件，请根据需要修改配置"
fi

# 创建数据目录
mkdir -p data

# 启动服务
echo "📦 安装依赖..."
uv sync

echo "🌐 启动服务..."
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo "✨ 服务已启动：http://localhost:8000"
echo "📚 API 文档：http://localhost:8000/docs"
echo "🏥 健康检查：http://localhost:8000/health"
