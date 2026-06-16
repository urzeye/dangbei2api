# Dangbei2API

将[当贝 AI](https://ai.dangbei.com/chat) 网页版能力封装为 OpenAI 兼容 API。

## 功能

- ✅ `/chat/completions` — OpenAI Chat Completions 格式（流式 + 非流式）
- ✅ `/v1/response` — OpenAI Response API 格式（流式 + 非流式）
- ✅ `/v1/models` — 模型列表
- ✅ 支持联网搜索 (`online`) 和深度思考 (`deep`)
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

### Chat Completions

```bash
curl http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### 联网搜索

```bash
curl http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5",
    "messages": [{"role": "user", "content": "今天天气怎么样"}],
    "stream": true,
    "user_action": "online"
  }'
```

### 深度思考 + 联网

```bash
curl http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5",
    "messages": [{"role": "user", "content": "三体讲的是什么"}],
    "stream": true,
    "user_action": "online,deep"
  }'
```

### Response API

```bash
curl http://localhost:8000/v1/response \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3",
    "input": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
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

## 配置说明

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DANGBEI_BASE_URL` | `https://ai-api.dangbei.net` | 当贝 API 地址 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `DEFAULT_MODEL` | `deepseek-v3` | 默认模型 |
| `DANGBEI_TOKEN` | (空) | 登录 token，匿名模式留空 |

## 架构

```
用户请求 (OpenAI 格式)
    │
    ▼
app/routes.py          ← FastAPI 路由，参数校验
    │
    ▼
app/dangbei_client.py  ← 调用当贝 API（创建会话 → 生成 ID → SSE 聊天）
    │
    ▼
app/converters.py      ← SSE 事件 → OpenAI / Response 格式转换
    │
    ▼
用户响应 (OpenAI 格式 SSE / JSON)
```

## 限制

- **匿名模式**：每次请求自动换 deviceid，不支持文件上传
- **登录模式**：配置 `DANGBEI_TOKEN` 后可上传文件（需额外实现 OSS 上传链路）
- **深度思考**：匿名模式下思考过程不单独流式输出，仅返回最终答案
- **会话隔离**：每次 `/chat/completions` 请求创建新会话，不支持多轮对话上下文
