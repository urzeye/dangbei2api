"""
Route handlers - 优化版本。

改进：
1. 使用新的会话存储抽象
2. 使用 dangbei_client 的上下文管理器
3. 添加限流保护
4. 统一错误处理
5. 添加健康检查
6. 模型列表缓存
7. 消除重复代码
"""

import json
import time
import uuid as uuid_lib
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from app import converters, dangbei_client
from app.errors import DangbeiAPIError, validate_request
from app.logger import get_logger
from app.models import (
    ChatCompletionRequest,
    ModelInfo,
    ModelListResponse,
    ResponseInputItem,
    ResponseRequest,
)
from app.session_store import get_session_store
from app.settings import settings
from app.utils import extract_user_question, parse_model_and_action

logger = get_logger(__name__)
router = APIRouter()

# 限流器
limiter = Limiter(key_func=get_remote_address)

# API Key 鉴权
_security = HTTPBearer(auto_error=False)

# 未提供 user 字段时的默认会话 key
_DEFAULT_USER_KEY = "__default__"

# Response API 会话映射（response_id → conversation_id）
_response_store: dict[str, str] = {}


def _verify_api_key(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> None:
    """验证 Bearer Token，未配置 API_KEY 时跳过"""
    if not settings.api_key:
        return  # 免验证模式

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="缺少 API Key，请通过 Authorization: Bearer <key> 提供"
        )

    if credentials.credentials != settings.api_key:
        raise HTTPException(status_code=403, detail="API Key 无效")


async def _get_or_create_conversation(user: str | None) -> str:
    """
    基于 user 字段获取或创建会话。

    - user 为 None 或空字符串 → 使用默认 key 复用同一会话
    - user 有值 → 查找 session_store，存在则复用，不存在则创建
    """
    store = await get_session_store()
    effective_user = user if user else _DEFAULT_USER_KEY

    # 尝试获取已有会话
    conversation_id = await store.get(effective_user)
    if conversation_id:
        logger.debug("复用已有会话", user=effective_user, conversation_id=conversation_id)
        return conversation_id

    # 创建新会话
    conversation_id = await dangbei_client.create_conversation()
    await store.set(effective_user, conversation_id)
    logger.info("创建新会话", user=effective_user, conversation_id=conversation_id)
    return conversation_id


async def _resolve_conversation_for_response(
    previous_response_id: str | None,
    user: str | None,
) -> tuple[str, bool]:
    """
    为 /v1/response 解析 conversation_id。

    优先级：previous_response_id > user > 默认会话 > 新建
    返回 (conversation_id, is_new)
    """
    store = await get_session_store()

    # 1. 通过 previous_response_id 查找
    if previous_response_id and previous_response_id in _response_store:
        conversation_id = _response_store[previous_response_id]
        logger.debug("通过 response_id 复用会话", conversation_id=conversation_id)
        return conversation_id, False

    # 2. 通过 user 查找（含默认 key）
    effective_user = user if user else _DEFAULT_USER_KEY
    conversation_id = await store.get(effective_user)
    if conversation_id:
        logger.debug("通过 user 复用会话", user=effective_user, conversation_id=conversation_id)
        return conversation_id, False

    # 3. 新建会话
    conversation_id = await dangbei_client.create_conversation()
    await store.set(effective_user, conversation_id)
    logger.info("为 Response API 创建新会话", user=effective_user, conversation_id=conversation_id)
    return conversation_id, True


# ============================================================
# 健康检查
# ============================================================

@router.get("/health")
async def health_check():
    """
    健康检查端点。

    检查：
    - 服务运行状态
    - 当贝 API 连通性
    - 会话存储状态
    """
    health_status = {
        "status": "healthy",
        "timestamp": int(time.time()),
        "version": "0.2.0",
    }

    # 检查当贝 API 连通性
    try:
        await dangbei_client.get_http_client()
        health_status["dangbei_api"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dangbei_api"] = f"error: {e}"

    # 检查会话存储
    try:
        store = await get_session_store()
        sessions = await store.list_all()
        health_status["session_store"] = {
            "type": "sqlite" if settings.use_sqlite_session else "memory",
            "active_sessions": len(sessions),
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["session_store"] = f"error: {e}"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


# ============================================================
# /v1/models
# ============================================================

# 模型列表缓存（避免频繁请求当贝 API）
_model_cache: tuple[float, ModelListResponse] | None = None


@router.get("/v1/models")
async def list_models(_auth: None = Depends(_verify_api_key)):
    """
    列出当贝可用模型（OpenAI 格式）。

    根据 getChatModelConfig 返回的 option[].disable 精确追加功能变体。
    结果会缓存一段时间以提高性能。
    """
    global _model_cache

    # 检查缓存
    now = time.time()
    if _model_cache is not None:
        cache_time, cached_response = _model_cache
        if now - cache_time < settings.model_cache_ttl:
            logger.debug("使用模型列表缓存")
            return cached_response

    # 获取最新模型列表
    try:
        models = await dangbei_client.get_model_list()
    except DangbeiAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=f"获取模型列表失败: {e.message}")

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

    response = ModelListResponse(data=data)

    # 更新缓存
    _model_cache = (now, response)
    logger.info("模型列表已缓存", count=len(data), ttl=settings.model_cache_ttl)

    return response


# ============================================================
# 会话管理端点
# ============================================================

@router.delete("/v1/conversations")
async def reset_all_conversations(_auth: None = Depends(_verify_api_key)):
    """清空所有会话，重新开始"""
    store = await get_session_store()
    user_count = await store.clear()
    response_count = len(_response_store)
    _response_store.clear()

    logger.info("清空所有会话", user_count=user_count, response_count=response_count)

    return {
        "message": "所有会话已清空",
        "cleared_users": user_count,
        "cleared_responses": response_count,
    }


@router.delete("/v1/conversations/{user}")
async def reset_user_conversation(user: str, _auth: None = Depends(_verify_api_key)):
    """清空指定 user 的会话"""
    store = await get_session_store()
    deleted = await store.delete(user)

    if deleted:
        logger.info("清空用户会话", user=user)
        return {"message": f"会话 '{user}' 已清空"}

    sessions = await store.list_all()
    available_users = [s[0] for s in sessions]
    return {"message": f"会话 '{user}' 不存在", "available_users": available_users}


@router.get("/v1/conversations")
async def list_conversations(_auth: None = Depends(_verify_api_key)):
    """列出当前所有活跃会话及其最后访问时间"""
    store = await get_session_store()
    sessions_data = await store.list_all()

    now = time.time()
    sessions = []
    for user, conv_id, last_time in sessions_data:
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
        "expire_seconds": settings.session_expire_seconds if settings.session_expire_seconds > 0 else None,
    }


# ============================================================
# /v1/chat/completions
# ============================================================

@router.post("/v1/chat/completions")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute" if settings.rate_limit_enabled else "1000000/minute")
async def chat_completions(
    request: Request,
    req: ChatCompletionRequest,
    _auth: None = Depends(_verify_api_key)
):
    """
    OpenAI 兼容 /v1/chat/completions 端点。

    支持流式 (SSE) 和非流式。
    - 模型名后缀控制 userAction
    - user 字段控制会话保持
    - 零自定义 Header
    """
    question = extract_user_question(req.messages)
    validate_request(bool(question), "至少需要一条 user 消息")

    # 从模型名解析 base_model 和 user_action
    model = req.model or settings.default_model
    base_model, user_action = parse_model_and_action(model)

    # 基于 user 字段获取或创建会话
    conversation_id = await _get_or_create_conversation(req.user)
    chat_id = await dangbei_client.generate_id()

    logger.info(
        "处理 chat.completions 请求",
        model=base_model,
        user_action=user_action,
        stream=req.stream,
        user=req.user or _DEFAULT_USER_KEY,
    )

    # 流式响应
    if req.stream:
        async def event_stream():
            try:
                async with dangbei_client.chat_sse_stream(
                    conversation_id=conversation_id,
                    chat_id=chat_id,
                    question=question,
                    model=base_model,
                    user_action=user_action,
                ) as stream:
                    async for chunk in converters.sse_to_openai_stream(stream, model):
                        yield chunk
            except DangbeiAPIError as e:
                error_chunk = json.dumps({
                    "error": {"message": str(e.message), "type": "dangbei_error"}
                }, ensure_ascii=False)
                yield f"data: {error_chunk}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 非流式响应
    try:
        async with dangbei_client.chat_sse_stream(
            conversation_id=conversation_id,
            chat_id=chat_id,
            question=question,
            model=base_model,
            user_action=user_action,
        ) as stream:
            result = await converters.sse_to_openai_full(stream, model)
            result["_conversation_id"] = conversation_id
            return JSONResponse(content=result)
    except DangbeiAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ============================================================
# /v1/responses
# ============================================================

@router.post("/v1/responses")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute" if settings.rate_limit_enabled else "1000000/minute")
async def responses_api(
    request: Request,
    req: ResponseRequest,
    _auth: None = Depends(_verify_api_key)
):
    """
    OpenAI 兼容 /v1/responses 端点。

    支持流式 (SSE) 和非流式。
    - 模型名后缀控制 userAction
    - previous_response_id 标准字段支持多轮对话
    - user 字段支持会话保持
    """
    user_inputs = [item for item in req.input if item.role == "user"]
    validate_request(bool(user_inputs), "至少需要一条 user 输入")
    question = user_inputs[-1].content

    # 从模型名解析 base_model 和 user_action
    model = req.model or settings.default_model
    base_model, user_action = parse_model_and_action(model)

    # 解析会话
    conversation_id, is_new = await _resolve_conversation_for_response(
        req.previous_response_id, req.user
    )
    chat_id = await dangbei_client.generate_id()

    # 生成 response_id 并建立映射
    response_id = f"resp_{uuid_lib.uuid4().hex[:24]}"
    _response_store[response_id] = conversation_id

    logger.info(
        "处理 responses 请求",
        model=base_model,
        user_action=user_action,
        stream=req.stream,
        user=req.user or _DEFAULT_USER_KEY,
        is_new_conversation=is_new,
    )

    # 流式响应
    if req.stream:
        async def event_stream():
            try:
                async with dangbei_client.chat_sse_stream(
                    conversation_id=conversation_id,
                    chat_id=chat_id,
                    question=question,
                    model=base_model,
                    user_action=user_action,
                ) as stream:
                    async for chunk in converters.sse_to_response_stream(stream, model, response_id):
                        yield chunk
            except DangbeiAPIError as e:
                error_event = json.dumps({
                    "type": "error",
                    "error": {"message": str(e.message), "type": "dangbei_error"},
                }, ensure_ascii=False)
                yield f"event: error\ndata: {error_event}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 非流式响应
    try:
        async with dangbei_client.chat_sse_stream(
            conversation_id=conversation_id,
            chat_id=chat_id,
            question=question,
            model=base_model,
            user_action=user_action,
        ) as stream:
            result = await converters.sse_to_response_full(stream, model, response_id)
            result["_conversation_id"] = conversation_id
            return JSONResponse(content=result)
    except DangbeiAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
