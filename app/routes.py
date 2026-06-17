"""
Route handlers — 完整兼容 OpenAI /v1/chat/completions 和 /v1/responses 协议。

当贝专有参数通过标准 OpenAI 字段承载（零自定义 Header）：
  - userAction (online/deep): 模型名后缀，如 deepseek-v3-online-deep
  - 会话保持: user 字段（相同 user 值复用同一 conversationId）
  - /v1/responses 多轮: previous_response_id（标准字段）
"""

from __future__ import annotations

import json
import time
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import converters, dangbei_client
from app.config import API_KEY, DEFAULT_MODEL, SESSION_EXPIRE_SECONDS
from app.models import (
    ChatCompletionRequest,
    Message,
    ModelInfo,
    ModelListResponse,
    ResponseRequest,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# API Key 鉴权（可选）
#   - 未配置 API_KEY → 免验证，向后兼容
#   - 配置了 API_KEY → 必须带 Authorization: Bearer <key>
# ---------------------------------------------------------------------------
_security = HTTPBearer(auto_error=False)


def _verify_api_key(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> None:
    """验证 Bearer Token，未配置 API_KEY 时跳过。"""
    if not API_KEY:
        return  # 免验证模式
    if credentials is None:
        raise HTTPException(status_code=401, detail="缺少 API Key，请通过 Authorization: Bearer <key> 提供")
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=403, detail="API Key 无效")

# ---------------------------------------------------------------------------
# 会话映射表（内存）
#   user_store:      user 值 → (conversation_id, last_access_time)
#   response_store:  response_id → conversation_id（用于 /v1/response）
# ---------------------------------------------------------------------------
user_store: dict[str, tuple[str, float]] = {}  # user → (conversation_id, timestamp)
response_store: dict[str, str] = {}            # response_id → conversation_id

# 未提供 user 字段时的默认会话 key（服务生命周期内复用同一会话）
_DEFAULT_USER_KEY = "__default__"


def _cleanup_expired_sessions() -> None:
    """清理过期会话（仅在 SESSION_EXPIRE_SECONDS > 0 时生效）"""
    if SESSION_EXPIRE_SECONDS <= 0:
        return

    now = time.time()
    expired_users = [
        user for user, (_, last_time) in user_store.items()
        if now - last_time > SESSION_EXPIRE_SECONDS
    ]
    for user in expired_users:
        del user_store[user]


# ============================================================
# 辅助函数
# ============================================================

def _extract_user_question(messages: list[Message]) -> str:
    """从 messages 数组中提取最后一条 user 消息的文本内容。"""
    for m in reversed(messages):
        if m.role == "user" and isinstance(m.content, str):
            return m.content
    return ""


def _parse_model_and_action(model: str) -> tuple[str, str]:
    """
    从模型名解析出实际当贝模型名和 userAction。

    >>> _parse_model_and_action("deepseek-v3-online-deep")
    ("deepseek-v3", "online,deep")
    >>> _parse_model_and_action("deepseek-v3-online")
    ("deepseek-v3", "online")
    >>> _parse_model_and_action("deepseek-v3-deep")
    ("deepseek-v3", "deep")
    >>> _parse_model_and_action("deepseek-v3")
    ("deepseek-v3", "online,deep")   # 默认开启联网+深度思考
    """
    known_suffixes = ["-online-deep", "-deep-online", "-online", "-deep", "-basic"]
    for suffix in known_suffixes:
        if model.endswith(suffix):
            base = model[: -len(suffix)]
            action = suffix[1:]  # 去掉前导 "-"
            if action in ("deep-online", "online-deep"):
                action = "online,deep"
            elif action == "basic":
                action = ""
            return base, action
    # 无已知后缀 → 默认开启 online + deep
    return model, "online,deep"


async def _get_or_create_conversation(user: str | None) -> str:
    """
    基于 user 字段获取或创建会话。

    - user 为 None 或空字符串 → 使用默认 key 复用同一会话（有状态模式）
    - user 有值 → 查找 user_store，存在则复用，不存在则创建并存入
    - 自动清理过期会话（SESSION_EXPIRE_SECONDS > 0 时生效）
    """
    _cleanup_expired_sessions()  # 每次请求时清理过期会话

    effective_user = user if user else _DEFAULT_USER_KEY

    if effective_user in user_store:
        conversation_id, _ = user_store[effective_user]
        user_store[effective_user] = (conversation_id, time.time())  # 更新访问时间
        return conversation_id

    conversation_id = await dangbei_client.create_conversation()
    user_store[effective_user] = (conversation_id, time.time())
    return conversation_id


async def _resolve_conversation_for_response(
    previous_response_id: str | None,
    user: str | None,
) -> tuple[str, bool]:
    """
    为 /v1/response 解析 conversation_id。

    优先级：previous_response_id > user > 默认会话 > 新建

    返回 (conversation_id, is_new)。
    """
    _cleanup_expired_sessions()  # 每次请求时清理过期会话

    # 1. 通过 previous_response_id 查找
    if previous_response_id and previous_response_id in response_store:
        conversation_id = response_store[previous_response_id]
        # 更新对应 user 的访问时间
        for user_key, (conv_id, _) in user_store.items():
            if conv_id == conversation_id:
                user_store[user_key] = (conv_id, time.time())
                break
        return conversation_id, False

    # 2. 通过 user 查找（含默认 key）
    effective_user = user if user else _DEFAULT_USER_KEY
    if effective_user in user_store:
        conversation_id, _ = user_store[effective_user]
        user_store[effective_user] = (conversation_id, time.time())  # 更新访问时间
        return conversation_id, False

    # 3. 新建会话
    conversation_id = await dangbei_client.create_conversation()
    user_store[effective_user] = (conversation_id, time.time())
    return conversation_id, True


# ============================================================
# /v1/models
# ============================================================

@router.get("/v1/models")
async def list_models(_auth: None = Depends(_verify_api_key)):
    """
    列出当贝可用模型（OpenAI 格式）。

    根据 getChatModelConfig 返回的 option[].disable 精确追加功能变体：
    - 仅当 deep 的 disable=false 时才追加 -deep / -online-deep 变体
    - 仅当 online 的 disable=false 时才追加 -online / -online-deep 变体
    - -basic（无功能）始终可用
    """
    try:
        models = await dangbei_client.get_model_list()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取模型列表失败: {e}")

    data: list[ModelInfo] = []
    for m in models:
        model_id = m["value"]
        # 解析 option 数组，获取各能力的 disable 状态
        options = m.get("option", [])
        cap_disable: dict[str, bool] = {}
        for opt in options:
            cap_disable[opt.get("value", "")] = opt.get("disable", True)

        has_deep = not cap_disable.get("deep", True)
        has_online = not cap_disable.get("online", True)

        # 基础模型（无后缀 → 默认行为：有能力的自动开启）
        data.append(ModelInfo(id=model_id))
        # -basic：强制关闭所有能力
        data.append(ModelInfo(id=f"{model_id}-basic"))

        if has_online and has_deep:
            data.append(ModelInfo(id=f"{model_id}-online-deep"))
        if has_online:
            data.append(ModelInfo(id=f"{model_id}-online"))
        if has_deep:
            data.append(ModelInfo(id=f"{model_id}-deep"))

    return ModelListResponse(data=data)


# ============================================================
# 会话管理端点
# ============================================================

@router.delete("/v1/conversations")
async def reset_all_conversations(_auth: None = Depends(_verify_api_key)):
    """
    清空所有会话，重新开始。

    场景：想要重置默认会话或清理所有用户会话时使用。
    """
    user_count = len(user_store)
    response_count = len(response_store)
    user_store.clear()
    response_store.clear()
    return {
        "message": "所有会话已清空",
        "cleared_users": user_count,
        "cleared_responses": response_count,
    }


@router.delete("/v1/conversations/{user}")
async def reset_user_conversation(user: str, _auth: None = Depends(_verify_api_key)):
    """
    清空指定 user 的会话。

    Args:
        user: 用户标识，传 "__default__" 可清空默认会话
    """
    if user in user_store:
        del user_store[user]
        return {"message": f"会话 '{user}' 已清空"}
    return {"message": f"会话 '{user}' 不存在", "available_users": list(user_store.keys())}


@router.get("/v1/conversations")
async def list_conversations(_auth: None = Depends(_verify_api_key)):
    """
    列出当前所有活跃会话及其最后访问时间。
    """
    now = time.time()
    sessions = []
    for user, (conv_id, last_time) in user_store.items():
        idle_seconds = int(now - last_time)
        sessions.append({
            "user": user,
            "conversation_id": conv_id,
            "last_access": idle_seconds,
            "idle_seconds": idle_seconds,
        })
    return {
        "total": len(sessions),
        "sessions": sessions,
        "expire_seconds": SESSION_EXPIRE_SECONDS if SESSION_EXPIRE_SECONDS > 0 else None,
    }


# ============================================================
# /v1/chat/completions
# ============================================================

@router.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, _auth: None = Depends(_verify_api_key)):
    """
    OpenAI 兼容 /v1/chat/completions 端点。

    支持流式 (SSE) 和非流式。
    - 模型名后缀控制 userAction：deepseek-v3-online-deep → 联网+深度思考
    - user 字段控制会话保持：相同 user 值复用同一 conversationId
    - 零自定义 Header
    """
    question = _extract_user_question(req.messages)
    if not question:
        raise HTTPException(status_code=400, detail="至少需要一条 user 消息")

    # 从模型名解析 base_model 和 user_action
    model = req.model or DEFAULT_MODEL
    base_model, user_action = _parse_model_and_action(model)

    # 基于 user 字段获取或创建会话
    try:
        conversation_id = await _get_or_create_conversation(req.user)
        chat_id = await dangbei_client.generate_id()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"当贝 API 错误: {e}")

    # ------------------------------------------------------------------
    # 流式响应
    # ------------------------------------------------------------------
    if req.stream:
        async def event_stream():
            response = None
            try:
                response = await dangbei_client.chat_sse(
                    conversation_id=conversation_id,
                    chat_id=chat_id,
                    question=question,
                    model=base_model,
                    user_action=user_action,
                )
                async for chunk in converters.sse_to_openai_stream(
                    response.aiter_lines(), model
                ):
                    yield chunk
            except Exception as e:
                error_chunk = json.dumps({
                    "error": {"message": str(e), "type": "dangbei_error"}
                }, ensure_ascii=False)
                yield f"data: {error_chunk}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                if response is not None:
                    await response.aclose()
                    if hasattr(response, '_client'):
                        await response._client.aclose()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------
    # 非流式响应
    # ------------------------------------------------------------------
    response = None
    try:
        response = await dangbei_client.chat_sse(
            conversation_id=conversation_id,
            chat_id=chat_id,
            question=question,
            model=base_model,
            user_action=user_action,
        )
        result = await converters.sse_to_openai_full(
            response.aiter_lines(), model
        )
        # 在响应中附加 conversation_id（通过 _conversation_id 内部字段）
        result["_conversation_id"] = conversation_id
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"当贝 API 错误: {e}")
    finally:
        if response is not None:
            await response.aclose()
            if hasattr(response, '_client'):
                await response._client.aclose()


# ============================================================
# /v1/responses
# ============================================================

@router.post("/v1/responses")
async def responses_api(req: ResponseRequest, _auth: None = Depends(_verify_api_key)):
    """
    OpenAI 兼容 /v1/responses 端点。

    支持流式 (SSE) 和非流式。
    - 模型名后缀控制 userAction
    - previous_response_id 标准字段支持多轮对话
    - user 字段支持会话保持
    - 零自定义 Header
    """
    user_inputs = [item for item in req.input if item.role == "user"]
    if not user_inputs:
        raise HTTPException(status_code=400, detail="至少需要一条 user 输入")
    question = user_inputs[-1].content

    # 从模型名解析 base_model 和 user_action
    model = req.model or DEFAULT_MODEL
    base_model, user_action = _parse_model_and_action(model)

    # 解析会话
    try:
        conversation_id, is_new = await _resolve_conversation_for_response(
            req.previous_response_id, req.user
        )
        chat_id = await dangbei_client.generate_id()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"当贝 API 错误: {e}")

    # 生成 response_id 并建立映射
    response_id = f"resp_{uuid_lib.uuid4().hex[:24]}"
    response_store[response_id] = conversation_id

    # ------------------------------------------------------------------
    # 流式响应
    # ------------------------------------------------------------------
    if req.stream:
        async def event_stream():
            resp = None
            try:
                resp = await dangbei_client.chat_sse(
                    conversation_id=conversation_id,
                    chat_id=chat_id,
                    question=question,
                    model=base_model,
                    user_action=user_action,
                )
                async for chunk in converters.sse_to_response_stream(
                    resp.aiter_lines(), model, response_id
                ):
                    yield chunk
            except Exception as e:
                error_event = json.dumps({
                    "type": "error",
                    "error": {"message": str(e), "type": "dangbei_error"},
                }, ensure_ascii=False)
                yield f"event: error\ndata: {error_event}\n\n"
            finally:
                if resp is not None:
                    await resp.aclose()
                    if hasattr(resp, '_client'):
                        await resp._client.aclose()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------
    # 非流式响应
    # ------------------------------------------------------------------
    resp = None
    try:
        resp = await dangbei_client.chat_sse(
            conversation_id=conversation_id,
            chat_id=chat_id,
            question=question,
            model=base_model,
            user_action=user_action,
        )
        result = await converters.sse_to_response_full(
            resp.aiter_lines(), model, response_id
        )
        result["_conversation_id"] = conversation_id
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"当贝 API 错误: {e}")
    finally:
        if resp is not None:
            await resp.aclose()
            if hasattr(resp, '_client'):
                await resp._client.aclose()

