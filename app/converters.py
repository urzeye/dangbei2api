"""
SSE event parsers and format converters.

Dangbei SSE events:
  - conversation.message.delta  → content_type: text | card | progress
  - conversation.chat.completed → final marker
"""

import json
import time
import uuid as uuid_lib
from typing import AsyncIterator, Optional


def _make_openai_chunk(
    delta_content: str,
    model: str,
    chunk_id: str,
    role: str = "assistant",
    finish_reason: Optional[str] = None,
) -> dict:
    """Build an OpenAI-compatible streaming chunk."""
    chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": delta_content} if delta_content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    if not delta_content and finish_reason is None:
        chunk["choices"][0]["delta"] = {"role": role}
    return chunk


def _make_openai_final(chunk_id: str, model: str) -> dict:
    """Build the final [DONE] marker chunk."""
    return {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {"index": 0, "delta": {}, "finish_reason": "stop"}
        ],
    }


def _make_response_event(
    event_type: str,
    text: str = "",
    item_id: Optional[str] = None,
    output_index: int = 0,
    content_index: int = 0,
) -> dict:
    """Build an OpenAI Response API SSE event."""
    base = {
        "type": event_type,
    }
    if event_type == "response.output_text.delta":
        base["item_id"] = item_id
        base["output_index"] = output_index
        base["content_index"] = content_index
        base["delta"] = text
    elif event_type == "response.output_text.done":
        base["item_id"] = item_id
        base["output_index"] = output_index
        base["content_index"] = content_index
        base["text"] = text
    elif event_type == "response.completed":
        base["response"] = {
            "id": f"resp_{uuid_lib.uuid4().hex[:24]}",
            "object": "response",
            "status": "completed",
            "output": [],
        }
    return base


async def sse_to_openai_stream(
    sse_lines: AsyncIterator[str],
    model: str,
) -> AsyncIterator[str]:
    """
    Convert Dangbei SSE lines to OpenAI /chat/completions streaming format.

    Yields SSE-formatted strings (including 'data: [DONE]').
    """
    chunk_id = f"chatcmpl-{uuid_lib.uuid4().hex[:24]}"
    started = False
    full_text = ""

    async for line in sse_lines:
        line = line.strip()
        if not line:
            continue

        # Parse SSE: "event:..." or "data:..."
        if line.startswith("event:"):
            continue  # event type line, skip

        if not line.startswith("data:"):
            continue

        data_str = line[5:].strip()
        if not data_str:
            continue

        try:
            event_data = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        content_type = event_data.get("content_type", "")
        content = event_data.get("content", "")

        if content_type == "text":
            if not started:
                # First text chunk: send role
                role_chunk = _make_openai_chunk("", model, chunk_id, role="assistant")
                yield f"data: {json.dumps(role_chunk, ensure_ascii=False)}\n\n"
                started = True
            full_text += content
            chunk = _make_openai_chunk(content, model, chunk_id)
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        elif content_type == "card":
            # Search result card — skip in text stream, or could be injected as system note
            pass

        elif content_type == "progress":
            # Progress messages — skip in text stream
            pass

    # Send final chunk
    if not started:
        # No text was ever produced, send empty role + finish
        role_chunk = _make_openai_chunk("", model, chunk_id, role="assistant")
        yield f"data: {json.dumps(role_chunk, ensure_ascii=False)}\n\n"

    final = _make_openai_final(chunk_id, model)
    yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


async def sse_to_response_stream(
    sse_lines: AsyncIterator[str],
    model: str,
) -> AsyncIterator[str]:
    """
    Convert Dangbei SSE lines to OpenAI /v1/response streaming format.

    Yields SSE-formatted strings.
    """
    item_id = f"item_{uuid_lib.uuid4().hex[:24]}"
    full_text = ""

    # Send initial response.created
    created = _make_response_event("response.created")
    yield f"event: response.created\ndata: {json.dumps(created, ensure_ascii=False)}\n\n"

    # Send output_item.added
    added = {
        "type": "response.output_item.added",
        "output_index": 0,
        "item": {
            "id": item_id,
            "object": "realtime.item",
            "type": "message",
            "status": "in_progress",
            "role": "assistant",
            "content": [],
        },
    }
    yield f"event: response.output_item.added\ndata: {json.dumps(added, ensure_ascii=False)}\n\n"

    # Send content_part.added
    part_added = {
        "type": "response.content_part.added",
        "item_id": item_id,
        "output_index": 0,
        "content_index": 0,
        "part": {"type": "output_text", "text": ""},
    }
    yield f"event: response.content_part.added\ndata: {json.dumps(part_added, ensure_ascii=False)}\n\n"

    async for line in sse_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            continue
        if not line.startswith("data:"):
            continue

        data_str = line[5:].strip()
        if not data_str:
            continue

        try:
            event_data = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        content_type = event_data.get("content_type", "")
        content = event_data.get("content", "")

        if content_type == "text":
            full_text += content
            delta = _make_response_event(
                "response.output_text.delta",
                text=content,
                item_id=item_id,
            )
            yield f"event: response.output_text.delta\ndata: {json.dumps(delta, ensure_ascii=False)}\n\n"

        elif content_type in ("card", "progress"):
            pass

    # Send output_text.done
    text_done = _make_response_event(
        "response.output_text.done",
        text=full_text,
        item_id=item_id,
    )
    yield f"event: response.output_text.done\ndata: {json.dumps(text_done, ensure_ascii=False)}\n\n"

    # Send completed
    completed = _make_response_event("response.completed")
    yield f"event: response.completed\ndata: {json.dumps(completed, ensure_ascii=False)}\n\n"


async def sse_to_openai_full(
    sse_lines: AsyncIterator[str],
    model: str,
) -> dict:
    """
    Convert Dangbei SSE lines to a single OpenAI /chat/completions non-streaming response.
    """
    full_text = ""
    async for line in sse_lines:
        line = line.strip()
        if not line or line.startswith("event:") or not line.startswith("data:"):
            continue
        data_str = line[5:].strip()
        if not data_str:
            continue
        try:
            event_data = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        if event_data.get("content_type") == "text":
            full_text += event_data.get("content", "")

    return {
        "id": f"chatcmpl-{uuid_lib.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": full_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


async def sse_to_response_full(
    sse_lines: AsyncIterator[str],
    model: str,
) -> dict:
    """
    Convert Dangbei SSE lines to a single OpenAI /v1/response non-streaming response.
    """
    full_text = ""
    async for line in sse_lines:
        line = line.strip()
        if not line or line.startswith("event:") or not line.startswith("data:"):
            continue
        data_str = line[5:].strip()
        if not data_str:
            continue
        try:
            event_data = json.loads(data_str)
        except json.JSONDecodeError:
            continue
        if event_data.get("content_type") == "text":
            full_text += event_data.get("content", "")

    return {
        "id": f"resp_{uuid_lib.uuid4().hex[:24]}",
        "object": "response",
        "status": "completed",
        "model": model,
        "output": [
            {
                "id": f"item_{uuid_lib.uuid4().hex[:24]}",
                "object": "realtime.item",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": full_text,
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        },
    }
