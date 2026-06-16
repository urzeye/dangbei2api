"""
Route handlers for /chat/completions and /v1/response endpoints.
"""

import json
import uuid as uuid_lib
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from app.models import (
    ChatCompletionRequest,
    ResponseRequest,
    ModelListResponse,
    ModelInfo,
)
from app.config import DEFAULT_MODEL, DANGBEI_TOKEN
from app import dangbei_client
from app import converters

router = APIRouter()


# --- Helper: build user_action from request ---

def _resolve_user_action(request_action: str | None, model_caps: dict | None = None) -> str:
    """
    Resolve user_action from request. If not provided, default to empty.
    Could also intersect with model capabilities.
    """
    if request_action is not None:
        return request_action
    return ""


# --- /v1/models ---

@router.get("/v1/models")
async def list_models():
    """List available Dangbei models in OpenAI format."""
    try:
        models = await dangbei_client.get_model_list()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {e}")

    data = []
    for m in models:
        data.append(ModelInfo(id=m["value"]))
    return ModelListResponse(data=data)


# --- /chat/completions ---

@router.post("/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """
    OpenAI-compatible /chat/completions endpoint.
    Supports streaming (SSE) and non-streaming modes.
    """
    # Extract user message
    user_messages = [m for m in req.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="At least one user message is required")
    question = user_messages[-1].content

    model = req.model or DEFAULT_MODEL
    user_action = _resolve_user_action(req.user_action)

    # Check file upload permission
    if not DANGBEI_TOKEN:
        # Anonymous mode: no file upload support
        pass

    try:
        conversation_id = await dangbei_client.create_conversation()
        chat_id = await dangbei_client.generate_id()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dangbei API error: {e}")

    if req.stream:
        async def event_stream():
            client = None
            try:
                client = await dangbei_client.chat_sse(
                    conversation_id=conversation_id,
                    chat_id=chat_id,
                    question=question,
                    model=model,
                    user_action=user_action,
                )
                async for chunk in converters.sse_to_openai_stream(
                    client.aiter_lines(), model
                ):
                    yield chunk
            except Exception as e:
                error_chunk = json.dumps({
                    "error": {"message": str(e), "type": "dangbei_error"}
                }, ensure_ascii=False)
                yield f"data: {error_chunk}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                if client:
                    await client.aclose()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming
        client = None
        try:
            client = await dangbei_client.chat_sse(
                conversation_id=conversation_id,
                chat_id=chat_id,
                question=question,
                model=model,
                user_action=user_action,
            )
            result = await converters.sse_to_openai_full(client.aiter_lines(), model)
            return JSONResponse(content=result)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Dangbei API error: {e}")
        finally:
            if client:
                await client.aclose()


# --- /v1/response ---

@router.post("/v1/response")
async def response_api(req: ResponseRequest):
    """
    OpenAI-compatible /v1/response endpoint.
    Supports streaming (SSE) and non-streaming modes.
    """
    # Extract user input
    user_inputs = [item for item in req.input if item.role == "user"]
    if not user_inputs:
        raise HTTPException(status_code=400, detail="At least one user input is required")
    question = user_inputs[-1].content

    model = req.model or DEFAULT_MODEL
    user_action = _resolve_user_action(req.user_action)

    try:
        conversation_id = await dangbei_client.create_conversation()
        chat_id = await dangbei_client.generate_id()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dangbei API error: {e}")

    if req.stream:
        async def event_stream():
            client = None
            try:
                client = await dangbei_client.chat_sse(
                    conversation_id=conversation_id,
                    chat_id=chat_id,
                    question=question,
                    model=model,
                    user_action=user_action,
                )
                async for chunk in converters.sse_to_response_stream(
                    client.aiter_lines(), model
                ):
                    yield chunk
            except Exception as e:
                error_event = json.dumps({
                    "type": "error",
                    "error": {"message": str(e), "type": "dangbei_error"},
                }, ensure_ascii=False)
                yield f"event: error\ndata: {error_event}\n\n"
            finally:
                if client:
                    await client.aclose()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        client = None
        try:
            client = await dangbei_client.chat_sse(
                conversation_id=conversation_id,
                chat_id=chat_id,
                question=question,
                model=model,
                user_action=user_action,
            )
            result = await converters.sse_to_response_full(client.aiter_lines(), model)
            return JSONResponse(content=result)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Dangbei API error: {e}")
        finally:
            if client:
                await client.aclose()
