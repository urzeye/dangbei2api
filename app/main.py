"""
Dangbei2API — 当贝 AI 网页版 → OpenAI 兼容 API 转发服务.

Usage:
    python -m app.main
    # or
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router
from app.config import HOST, PORT

app = FastAPI(
    title="Dangbei2API",
    description="将当贝 AI (ai.dangbei.com) 网页版能力封装为 OpenAI 兼容 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "Dangbei2API",
        "version": "0.1.0",
        "endpoints": {
            "/chat/completions": "OpenAI chat completions (stream & non-stream)",
            "/v1/response": "OpenAI Response API (stream & non-stream)",
            "/v1/models": "List available models",
        },
        "anonymous_mode": "No token configured — file upload disabled",
    }


def main():
    """Entry point for `uv run dangbei2api`."""
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)


if __name__ == "__main__":
    main()
