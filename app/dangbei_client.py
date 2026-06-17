"""
当贝 API 客户端 - 优化版本。

改进：
1. 使用全局连接池管理
2. 通过 async generator 自动管理资源
3. 添加结构化日志
4. 统一错误处理
"""

import uuid as uuid_lib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.errors import DangbeiAPIError
from app.logger import get_logger
from app.settings import settings

logger = get_logger(__name__)

# 全局 HTTP 客户端（连接池复用）
_http_client: httpx.AsyncClient | None = None


def _make_headers() -> dict:
    """构建请求头（包含 deviceid 和可选 token）"""
    headers = dict(settings.base_headers)
    headers["deviceid"] = f"dev_{uuid_lib.uuid4().hex[:16]}"
    if settings.dangbei_token:
        headers["token"] = settings.dangbei_token
        headers["deviceid"] = ""  # 登录模式：空 deviceid
    return headers


async def get_http_client() -> httpx.AsyncClient:
    """获取全局 HTTP 客户端（单例模式）"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout, connect=10.0),
            limits=httpx.Limits(
                max_connections=settings.http_max_connections,
                max_keepalive_connections=settings.http_max_keepalive,
            ),
            follow_redirects=True,
        )
        logger.info(
            "HTTP 客户端已创建",
            timeout=settings.http_timeout,
            max_connections=settings.http_max_connections,
        )
    return _http_client


async def close_http_client():
    """关闭全局 HTTP 客户端"""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        logger.info("HTTP 客户端已关闭")
        _http_client = None


async def create_conversation() -> str:
    """创建新会话，返回 conversationId"""
    url = f"{settings.dangbei_base_url}/ai-search/conversationApi/v1/batch/create"
    body = {
        "conversationList": [
            {
                "metaData": {"chatModelConfig": {}, "superAgentPath": "/chat"},
                "shareId": "",
                "isAnonymous": False,
                "source": "",
            }
        ]
    }

    client = await get_http_client()
    try:
        r = await client.post(url, json=body, headers=_make_headers())
        r.raise_for_status()
        data = r.json()

        if not data.get("success"):
            raise DangbeiAPIError(f"创建会话失败: {data}")

        conversation_id = data["data"]["conversationId"]
        logger.info("会话已创建", conversation_id=conversation_id)
        return conversation_id

    except httpx.HTTPStatusError as e:
        logger.error("创建会话 HTTP 错误", status_code=e.response.status_code)
        raise DangbeiAPIError(f"HTTP {e.response.status_code}", e.response.status_code)
    except httpx.RequestError as e:
        logger.error("创建会话网络错误", error=str(e))
        raise DangbeiAPIError(f"网络错误: {e}")


async def generate_id() -> str:
    """生成 chatId/uuid"""
    url = f"{settings.dangbei_base_url}/ai-search/commonApi/v1/generateId"

    client = await get_http_client()
    try:
        r = await client.post(url, json={}, headers=_make_headers())
        r.raise_for_status()
        data = r.json()

        if not data.get("success"):
            raise DangbeiAPIError(f"生成 ID 失败: {data}")

        return data["data"]

    except httpx.HTTPStatusError as e:
        logger.error("生成 ID HTTP 错误", status_code=e.response.status_code)
        raise DangbeiAPIError(f"HTTP {e.response.status_code}", e.response.status_code)
    except httpx.RequestError as e:
        logger.error("生成 ID 网络错误", error=str(e))
        raise DangbeiAPIError(f"网络错误: {e}")


@asynccontextmanager
async def chat_sse_stream(
    conversation_id: str,
    chat_id: str,
    question: str,
    model: str = "deepseek-v3",
    user_action: str = "",
    files: list | None = None,
) -> AsyncIterator[AsyncIterator[str]]:
    """
    发起流式聊天请求，返回 SSE 行迭代器。

    使用上下文管理器自动管理资源：
    ```python
    async with chat_sse_stream(...) as stream:
        async for line in stream:
            process(line)
    ```
    """
    url = f"{settings.dangbei_base_url}/ai-search/chatApi/v2/chat"
    body = {
        "stream": True,
        "botCode": "AI_SEARCH",
        "conversationId": conversation_id,
        "question": question,
        "content": question,
        "model": model,
        "userAction": user_action,
        "chatOption": {
            "searchKnowledge": False,
            "searchAllKnowledge": False,
            "searchSharedKnowledge": False,
        },
        "knowledgeList": [],
        "files": files or [],
        "reference": [],
        "anonymousKey": "",
        "uuid": chat_id,
        "chatId": chat_id,
        "role": "user",
        "status": "local",
        "agentId": "",
    }

    headers = _make_headers()
    headers["Accept"] = "text/event-stream"

    client = await get_http_client()

    logger.info(
        "开始流式聊天",
        conversation_id=conversation_id,
        chat_id=chat_id,
        model=model,
        user_action=user_action,
    )

    try:
        async with client.stream("POST", url, json=body, headers=headers) as response:
            response.raise_for_status()
            yield response.aiter_lines()

    except httpx.HTTPStatusError as e:
        logger.error(
            "聊天请求 HTTP 错误",
            status_code=e.response.status_code,
            conversation_id=conversation_id,
        )
        raise DangbeiAPIError(f"HTTP {e.response.status_code}", e.response.status_code)
    except httpx.RequestError as e:
        logger.error("聊天请求网络错误", error=str(e), conversation_id=conversation_id)
        raise DangbeiAPIError(f"网络错误: {e}")
    finally:
        logger.debug("流式聊天已结束", conversation_id=conversation_id)


async def get_model_list() -> list[dict]:
    """获取可用模型列表及其能力"""
    url = f"{settings.dangbei_base_url}/ai-search/configApi/v1/getChatModelConfig"

    client = await get_http_client()
    try:
        r = await client.get(url, headers=_make_headers())
        r.raise_for_status()
        data = r.json()

        if not data.get("success"):
            raise DangbeiAPIError(f"获取模型列表失败: {data}")

        models = data["data"]["modelList"]
        logger.info("模型列表已获取", count=len(models))
        return models

    except httpx.HTTPStatusError as e:
        logger.error("获取模型列表 HTTP 错误", status_code=e.response.status_code)
        raise DangbeiAPIError(f"HTTP {e.response.status_code}", e.response.status_code)
    except httpx.RequestError as e:
        logger.error("获取模型列表网络错误", error=str(e))
        raise DangbeiAPIError(f"网络错误: {e}")
