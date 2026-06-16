# Dangbei2API

将[当贝 AI](https://ai.dangbei.com/chat) 网页版能力封装为 OpenAI 兼容 API。

## 功能

- ✅ `/v1/chat/completions` — OpenAI Chat Completions 格式（流式 + 非流式）
- ✅ `/v1/response` — OpenAI Response API 格式（流式 + 非流式）
- ✅ `/v1/models` — 模型列表（自动追加功能变体）
- ✅ 支持联网搜索 (`online`) 和深度思考 (`deep`)
- ✅ **多轮对话**：通过标准 `user` 字段保持会话上下文
- ✅ **零自定义 Header**：完全使用 OpenAI 标准协议字段
- ✅ 匿名免登模式（自动换 deviceid 绕过配额限制）
- ⚠️ 文件上传需配置登录 token

## 快速开始

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

## API 使用

> **核心设计**：当贝专有参数通过标准 OpenAI 字段承载，无需任何自定义 Header。
> - `userAction` → 模型名后缀（如 `deepseek-v3-online-deep`）
> - 会话保持 → `user` 字段（相同值复用同一会话）
> - 多轮关联 → `previous_response_id`（标准字段）

### Chat Completions（基础）

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

### 多轮对话

通过标准 `user` 字段保持会话上下文，相同 `user` 值自动复用同一会话：

```bash
# 第一轮
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5-online-deep",
    "messages": [{"role": "user", "content": "我叫小明"}],
    "user": "alice"
  }'

# 第二轮 — 相同 user，自动记住上下文
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5-online-deep",
    "messages": [{"role": "user", "content": "我叫什么名字？"}],
    "user": "alice"
  }'
```

### Response API

```bash
curl http://localhost:8000/v1/response \
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
    api_key="dangbei-token",
)

# 默认开启联网+深度思考
response = client.chat.completions.create(
    model="glm-5-online-deep",
    messages=[{"role": "user", "content": "今天天气怎么样？"}],
    user="alice",  # 相同 user 保持会话
    stream=True,
)

# 多轮对话 — 相同 user，自动复用会话
r2 = client.chat.completions.create(
    model="glm-5-online-deep",
    messages=[{"role": "user", "content": "刚才说了什么？"}],
    user="alice",
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
| `DANGBEI_TOKEN` | (空) | 登录 token，匿名模式留空 |
| `DEFAULT_USER_ACTION` | `online,deep` | 默认行为（无后缀模型时生效） |

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
