"""
Pydantic models - 完整兼容 OpenAI /v1/chat/completions 和 /v1/response 协议。

当贝专有参数通过标准 OpenAI 字段承载：
  - userAction (online/deep): 模型名后缀，如 deepseek-v3-online-deep
  - 会话保持: user 字段（相同 user 值复用同一 conversationId）
  - /v1/response 多轮: previous_response_id（标准字段）
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================
# 通用
# ============================================================

class FunctionDef(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None  # JSON Schema
    strict: bool | None = None


class ToolDef(BaseModel):
    type: Literal["function"] = "function"
    function: FunctionDef


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: "ToolCallFunction"


class ToolCallFunction(BaseModel):
    name: str
    arguments: str  # JSON 字符串


# ============================================================
# /v1/chat/completions — 请求
# ============================================================

class Message(BaseModel):
    """单条消息，兼容 system / user / assistant / tool 四种角色。"""
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class ResponseFormat(BaseModel):
    type: Literal["text", "json_object", "json_schema"] = "text"
    json_schema: dict[str, Any] | None = None


class StreamOptions(BaseModel):
    include_usage: bool = False


class ChatCompletionRequest(BaseModel):
    """OpenAI /v1/chat/completions 完整请求模型"""
    model: str = Field(default="deepseek-v3", description="模型 ID，支持后缀控制功能（-online、-deep、-online-deep、-basic）")
    messages: list[Message] = Field(description="对话消息列表")
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0, description="频率惩罚")
    logit_bias: dict[str, float] | None = Field(default=None, description="Logit 偏置")
    logprobs: bool | None = Field(default=None, description="是否返回 log 概率")
    max_completion_tokens: int | None = Field(default=None, description="最大生成 token 数")
    max_tokens: int | None = Field(default=None, description="最大 token 数（已弃用，使用 max_completion_tokens）")
    n: int | None = Field(default=None, ge=1, description="生成的回复数量")
    parallel_tool_calls: bool | None = Field(default=None, description="是否并行调用工具")
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0, description="存在惩罚")
    response_format: ResponseFormat | None = Field(default=None, description="响应格式")
    seed: int | None = Field(default=None, description="随机种子")
    service_tier: Literal["auto", "default"] | None = Field(default=None, description="服务层级")
    stop: str | list[str] | None = Field(default=None, description="停止序列")
    stream: bool = Field(default=False, description="是否使用流式输出")
    stream_options: StreamOptions | None = Field(default=None, description="流式选项")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="温度参数")
    top_p: float | None = Field(default=None, ge=0.0, le=1.0, description="核采样参数")
    tools: list[ToolDef] | None = Field(default=None, description="可用工具列表")
    tool_choice: str | dict[str, Any] | None = Field(default=None, description="工具选择策略")
    user: str | None = Field(default=None, description="用户标识（用于会话隔离）")


    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "model": "deepseek-v3-online-deep",
                    "messages": [{"role": "user", "content": "你好"}],
                    "stream": True,
                    "user": "alice",
                }
            ]
        }
    }


# ============================================================
# /v1/chat/completions — 响应
# ============================================================

class ChatChoice(BaseModel):
    index: int
    message: Message
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"] | None = None
    logprobs: Any | None = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: Usage = Field(default_factory=Usage)
    system_fingerprint: str | None = None
    service_tier: str | None = None


# ============================================================
# /v1/response — 请求
# ============================================================

class ResponseInputItem(BaseModel):
    """Response API 的 input 数组元素。"""
    role: Literal["user", "assistant", "system", "developer"]
    content: str


class ResponseRequest(BaseModel):
    """OpenAI /v1/response 完整请求模型。"""
    model: str = "deepseek-v3"
    input: list[ResponseInputItem]
    instructions: str | None = None
    max_output_tokens: int | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stream: bool = False
    tools: list[ToolDef] | None = None
    tool_choice: str | dict[str, Any] | None = None
    previous_response_id: str | None = None
    user: str | None = None


# ============================================================
# /v1/response — 响应
# ============================================================

class OutputTextContent(BaseModel):
    type: Literal["output_text"] = "output_text"
    text: str


class ResponseOutputItem(BaseModel):
    id: str
    object: Literal["realtime.item"] = "realtime.item"
    type: Literal["message"] = "message"
    status: Literal["completed", "in_progress"] = "completed"
    role: Literal["assistant"] = "assistant"
    content: list[OutputTextContent] = Field(default_factory=list)


class ResponseUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ResponseResponse(BaseModel):
    id: str
    object: Literal["response"] = "response"
    created_at: int
    status: Literal["completed", "failed", "in_progress"] = "completed"
    model: str
    output: list[ResponseOutputItem] = Field(default_factory=list)
    usage: ResponseUsage = Field(default_factory=ResponseUsage)
    previous_response_id: str | None = None
    truncation: str = "disabled"
    incomplete_details: str | None = None
    parallel_tool_calls: bool = True


# ============================================================
# /v1/models
# ============================================================

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 1700000000
    owned_by: str = "dangbei"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]

