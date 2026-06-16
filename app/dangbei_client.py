import json
import uuid as uuid_lib
import httpx
from app.config import DANGBEI_BASE_URL, BASE_HEADERS, DANGBEI_TOKEN


def _make_headers() -> dict:
    """Build request headers with optional token and fresh deviceid."""
    headers = dict(BASE_HEADERS)
    headers["deviceid"] = f"dev_{uuid_lib.uuid4().hex[:16]}"
    if DANGBEI_TOKEN:
        headers["token"] = DANGBEI_TOKEN
        headers["deviceid"] = ""  # logged-in mode: empty deviceid
    return headers


async def create_conversation() -> str:
    """Create a new conversation, return conversationId."""
    url = f"{DANGBEI_BASE_URL}/ai-search/conversationApi/v1/batch/create"
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
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=body, headers=_make_headers())
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(f"createConversation failed: {data}")
        return data["data"]["conversationId"]


async def generate_id() -> str:
    """Generate a chatId/uuid for a new message."""
    url = f"{DANGBEI_BASE_URL}/ai-search/commonApi/v1/generateId"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={}, headers=_make_headers())
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(f"generateId failed: {data}")
        return data["data"]


async def chat_sse(
    conversation_id: str,
    chat_id: str,
    question: str,
    model: str = "deepseek-v3",
    user_action: str = "",
    files: list = None,
) -> httpx.Response:
    """
    发起流式聊天请求，返回 httpx.Response。

    调用方通过 response.aiter_lines() 迭代 SSE 行，
    用完后必须 await response.aclose() 关闭底层连接。

    注意：client 通过 response._client 挂载，调用方用完后需 await response._client.aclose()。
    """
    url = f"{DANGBEI_BASE_URL}/ai-search/chatApi/v2/chat"
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
    client = httpx.AsyncClient(timeout=300)
    response = await client.send(
        client.build_request("POST", url, json=body, headers=headers),
        stream=True,
    )
    response.raise_for_status()
    # 将 client 挂到 response 上，调用方用完需关闭
    response._client = client
    return response


async def get_model_list() -> list[dict]:
    """Fetch available models and their capabilities."""
    url = f"{DANGBEI_BASE_URL}/ai-search/configApi/v1/getChatModelConfig"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_make_headers())
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(f"getChatModelConfig failed: {data}")
        return data["data"]["modelList"]
