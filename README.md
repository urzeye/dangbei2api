# Dangbei2API

[![CI](https://github.com/urzeye/dangbei2api/actions/workflows/ci.yml/badge.svg)](https://github.com/urzeye/dangbei2api/actions/workflows/ci.yml)
[![Docker Build](https://github.com/urzeye/dangbei2api/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/urzeye/dangbei2api/actions/workflows/docker-publish.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/urzeye/dangbei2api)](https://hub.docker.com/r/urzeye/dangbei2api)
[![Release](https://img.shields.io/github/v/release/urzeye/dangbei2api)](https://github.com/urzeye/dangbei2api/releases)
[![License](https://img.shields.io/github/license/urzeye/dangbei2api)](LICENSE)

将[当贝 AI](https://ai.dangbei.com/chat) 网页版能力封装为 OpenAI 兼容 API。

> ⚠️ **免责声明**：本项目仅用于学习研究，严禁用于任何商业用途或违反当贝服务条款的行为。使用者须自行承担一切法律风险与责任。

## 功能特性

### 核心功能
- ✅ `/v1/chat/completions` — OpenAI Chat Completions 格式（流式 + 非流式）
- ✅ `/v1/responses` — OpenAI Responses API 格式（流式 + 非流式）
- ✅ `/v1/models` — 模型列表（自动追加功能变体）
- ✅ 支持联网搜索 (`online`) 和深度思考 (`deep`)
- ✅ **多轮对话**：默认共享会话（开箱即用有记忆），通过标准 `user` 字段实现会话隔离
- ✅ **零自定义 Header**：完全使用 OpenAI 标准协议字段
- ✅ **API Key 鉴权**：可选 `Authorization: Bearer` 验证，完全兼容 OpenAI SDK
- ✅ 匿名免登模式（自动换 deviceid 绕过配额限制）
- ⚠️ 文件上传需配置登录 token

### 生产级特性（v0.2.1 最新）
- 🚀 **连接池管理**：复用 HTTP 连接，提升性能
- 🔒 **限流保护**：可配置请求频率限制，防止滥用
- 📊 **结构化日志**：支持 JSON 格式输出，便于生产环境分析
- 💾 **会话持久化**：可选 SQLite 存储（默认内存），支持服务重启后恢复会话
- 🏥 **健康检查**：`/health` 端点，支持 Kubernetes/Docker 健康探测
- ⚡ **性能优化**：模型列表缓存、后台定期清理过期会话
- 🛡️ **统一错误处理**：OpenAI 兼容的错误响应格式
- 📦 **Docker 优化**：Alpine 镜像（~50MB）、健康检查、资源限制
- 🎯 **精确 Token 计算**：集成 tiktoken，提升计费准确性
- 🔍 **请求追踪**：每个请求自动生成 X-Request-ID，便于日志关联

## 快速开始

### 方式 1：Docker Hub（最快）

直接使用已构建好的镜像：

```bash
# 拉取最新版本
docker pull urzeye/dangbei2api:latest

# 运行容器（快速启动）
docker run -d -p 8000:8000 --name dangbei2api urzeye/dangbei2api:latest

# 运行容器（完整配置）
docker run -d -p 8000:8000 --name dangbei2api \
  -e API_KEY=your-secret-key \
  -e USE_SQLITE_SESSION=true \
  -v $(pwd)/data:/app/data \
  urzeye/dangbei2api:0.2.1

# 查看健康状态
curl http://localhost:8000/health
```

支持的镜像标签：
- `latest` - 最新稳定版
- `0.2.1` - 指定版本（推荐生产环境）
- `0.2` - 次版本号（自动获取最新补丁）

### 方式 2：Docker Compose（推荐自建）

```bash
# 1. 克隆项目
git clone https://github.com/urzeye/dangbei2api.git
cd dangbei2api

# 2. 启动服务（默认端口 8000）
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

### 方式 3：Docker 本地构建

```bash
# 构建镜像
docker build -t dangbei2api .

# 运行容器（内存会话）
docker run -d -p 8000:8000 --name dangbei2api dangbei2api

# 运行容器（SQLite 持久化会话）
docker run -d -p 8000:8000 --name dangbei2api \
  -v $(pwd)/data:/app/data \
  -e USE_SQLITE_SESSION=true \
  -e API_KEY=your-secret-key \
  dangbei2api

# 查看健康状态
curl http://localhost:8000/health
```

### 方式 4：本地运行

```bash
# 1. 安装依赖
uv sync

# 2. 配置（可选）
cp .env.example .env
# 编辑 .env，如需登录态上传文件则填入 DANGBEI_TOKEN

# 3. 启动
uv run python -m app.main
# 或
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 配置说明

所有配置通过环境变量设置，详见 `.env.example`。

### 核心配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DANGBEI_BASE_URL` | `https://ai-api.dangbei.net` | 当贝 API 地址 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `DEFAULT_MODEL` | `deepseek-v3` | 默认模型 |
| `API_KEY` | (空) | API 鉴权密钥，留空则不校验 |
| `DANGBEI_TOKEN` | (空) | 登录 token，匿名模式留空 |

### 会话管理

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `SESSION_EXPIRE_SECONDS` | `1800` | 会话过期时间（秒），0 表示永不过期 |
| `SESSION_CLEANUP_INTERVAL` | `300` | 会话清理任务间隔（秒） |
| `USE_SQLITE_SESSION` | `false` | 是否使用 SQLite 存储会话 |
| `SQLITE_DB_PATH` | `data/sessions.db` | SQLite 数据库文件路径 |

### 性能与限流

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `true` | 是否启用限流 |
| `RATE_LIMIT_PER_MINUTE` | `60` | 每分钟请求限制 |
| `HTTP_TIMEOUT` | `300` | HTTP 请求超时时间（秒） |
| `HTTP_MAX_CONNECTIONS` | `100` | HTTP 最大连接数 |
| `MODEL_CACHE_TTL` | `3600` | 模型列表缓存时间（秒） |

### 日志配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `LOG_LEVEL` | `INFO` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `LOG_JSON` | `false` | 是否输出 JSON 格式日志 |

## API 使用

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5-online-deep",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### 模型功能变体

通过模型名后缀控制联网搜索和深度思考，无需额外参数。

> **注意**：变体是否可用取决于模型自身能力。`/v1/models` 会根据当贝 API 返回的 `option.disable` 精确列出每个模型支持的变体，不支持的能力不会出现对应后缀。

| 请求模型名 | 效果 |
|-----------|------|
| `{model}-online-deep` | 联网搜索 + 深度思考 |
| `{model}-online` | 仅联网搜索 |
| `{model}-deep` | 仅深度思考 |
| `{model}-basic` | 基础模型，无联网无深度思考 |
| `{model}` | 无后缀，自动开启模型支持的能力 |

```bash
# 仅联网搜索
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5-online",
    "messages": [{"role": "user", "content": "今天天气怎么样"}],
    "stream": true
  }'

# 深度思考 + 联网
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5-online-deep",
    "messages": [{"role": "user", "content": "三体讲的是什么"}],
    "stream": true
  }'
```

### 多轮对话与会话隔离

**默认行为**：不传 `user` 字段时，所有请求共享同一个默认会话，开箱即用有记忆。

**会话隔离**：通过标准 `user` 字段为不同用户/对话创建独立会话，互不干扰。

**会话过期**：会话默认 30 分钟不活跃自动失效（可通过 `SESSION_EXPIRE_SECONDS` 配置），过期后下次请求自动创建新会话。

| 场景 | `user` 字段 | 行为 |
|------|------------|------|
| 不传 `user` | 空 | 共享默认会话（有记忆，30 分钟过期） |
| 传 `user: "alice"` | alice | alice 独立会话（有记忆，30 分钟过期） |
| 传 `user: "bob"` | bob | bob 独立会话（有记忆，与 alice 隔离） |

```bash
# === 默认会话（不传 user，共享） ===
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3-basic",
    "messages": [{"role": "user", "content": "我叫小明"}],
    "stream": false
  }'

# 第二轮 — 不传 user，复用默认会话，有记忆
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3-basic",
    "messages": [{"role": "user", "content": "我叫什么名字？"}],
    "stream": false
  }'
# → 回答：你叫小明 ✅

# === 独立会话（传 user，隔离） ===
# 会话 A
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3-basic",
    "messages": [{"role": "user", "content": "我叫小明"}],
    "user": "alice",
    "stream": false
  }'

# 会话 B — 不同 user，完全隔离
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3-basic",
    "messages": [{"role": "user", "content": "我叫什么名字？"}],
    "user": "bob",
    "stream": false
  }'
# → 回答：我不知道你的名字 ✅（隔离成功）

# 会话 A 第二轮 — 相同 user，有记忆
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3-basic",
    "messages": [{"role": "user", "content": "我叫什么名字？"}],
    "user": "alice",
    "stream": false
  }'
# → 回答：你叫小明 ✅
```

### 会话管理

**手动重置会话**：想要重新开始对话时，调用会话管理端点清空会话。

```bash
# 清空所有会话
curl -X DELETE http://localhost:8000/v1/conversations \
  -H "Authorization: Bearer your-secret-key"  # 配置了 API_KEY 时需要

# 清空指定用户会话
curl -X DELETE http://localhost:8000/v1/conversations/alice

# 清空默认会话（不传 user 时使用的会话）
curl -X DELETE http://localhost:8000/v1/conversations/__default__

# 查看当前活跃会话
curl http://localhost:8000/v1/conversations
```

**Shell 快捷命令**（可选）：

```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
alias reset-dangbei="curl -X DELETE http://localhost:8000/v1/conversations"

# 使用
reset-dangbei
```

> **注意**：会话存储在内存中，服务重启后所有会话丢失。同一 `user` 值始终映射到同一会话，如需同一用户开启多个独立对话，请使用不同的 `user` 值（如 `alice-work`、`alice-study`）。

### Response API

```bash
curl http://localhost:8000/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5-online-deep",
    "input": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### 标准 OpenAI SDK 调用

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-secret-key",  # 对应 .env 中的 API_KEY，未配置则随意填
)

# 默认共享会话（不传 user，开箱即用有记忆）
response = client.chat.completions.create(
    model="glm-5-online-deep",
    messages=[{"role": "user", "content": "今天天气怎么样？"}],
    stream=True,
)

# 多轮对话 — 不传 user，自动复用默认会话
r2 = client.chat.completions.create(
    model="glm-5-online-deep",
    messages=[{"role": "user", "content": "刚才说了什么？"}],
)

# 会话隔离 — 传 user 为不同用户创建独立会话
r3 = client.chat.completions.create(
    model="glm-5-online-deep",
    messages=[{"role": "user", "content": "你好"}],
    user="alice",  # alice 独立会话
)
```

## 可用模型

| 模型 ID | 名称 | 深度思考 | 联网 |
|---|---|---|---|
| `deepseek-v3` | DeepSeek-V3 | ✗ | ✓ |
| `glm-5` | GLM-5 | ✓ | ✓ |
| `qwen3-235b-a22b` | 通义3-235B | ✓ | ✓ |
| `kimi-k2-5` | Kimi K2-5 | ✗ | ✓ |
| `doubao` | 豆包 1.5-pro-32k | ✗ | ✓ |
| `qwen-plus` | 通义Plus | ✗ | ✓ |
| `qwq-plus` | 通义QwQ | ✓ | ✓ |
| `qwen-long` | 通义Long | ✗ | ✓ |
| `doubao-thinking` | 豆包-1.5-thinking-pro | ✓ | ✓ |
| `ernie-4.5-turbo-32k` | 文心4.5 | ✗ | ✓ |

> `/v1/models` 根据当贝 API 返回的 `option.disable` 精确追加变体。例如 `deepseek-v3` 不支持深度思考，则不会出现 `-deep` / `-online-deep` 后缀。

## 配置说明

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DANGBEI_BASE_URL` | `https://ai-api.dangbei.net` | 当贝 API 地址 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `DEFAULT_MODEL` | `deepseek-v3` | 默认模型 |
| `API_KEY` | (空) | API 鉴权密钥，留空则不校验 |
| `DANGBEI_TOKEN` | (空) | 登录 token，匿名模式留空 |
| `DEFAULT_USER_ACTION` | `online,deep` | 默认行为（无后缀模型时生效） |
| `SESSION_EXPIRE_SECONDS` | `1800` | 会话过期时间（秒），0 表示永不过期 |

### API Key 鉴权

设置 `API_KEY` 后，所有请求必须携带 `Authorization: Bearer <key>` 头，完全兼容 OpenAI SDK 的 `api_key` 参数：

```bash
# 不设置 API_KEY（默认）→ 免验证，任意 api_key 均可
# 设置 API_KEY=my-secret → 必须携带正确 key
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer my-secret"
```

## 架构

```
用户请求 (OpenAI 标准格式，零自定义 Header)
    │
    ▼
app/routes.py          ← FastAPI 路由，模型名后缀解析 → userAction
    │                     user 字段 → 会话映射，previous_response_id → 多轮关联
    ▼
app/dangbei_client.py  ← 调用当贝 API（创建会话 → 生成 ID → SSE 聊天）
    │
    ▼
app/converters.py      ← SSE 事件 → OpenAI / Response 格式转换
    │                     search_card 注入、token 用量估算
    ▼
用户响应 (OpenAI 格式 SSE / JSON)
```

## 限制

- **匿名模式**：每次请求自动换 deviceid，不支持文件上传
- **登录模式**：配置 `DANGBEI_TOKEN` 后可上传文件（需额外实现 OSS 上传链路）
- **深度思考**：匿名模式下思考过程不单独流式输出，仅返回最终答案
- **会话存储**：`user → conversationId` 映射存储在内存中，服务重启后丢失
- **会话过期**：默认 30 分钟不活跃自动失效，设置 `SESSION_EXPIRE_SECONDS=0` 可永久保留
