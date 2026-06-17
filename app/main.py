"""
Dangbei2API - 优化版本。

改进：
1. 使用 pydantic-settings 配置管理
2. 结构化日志
3. 全局异常处理
4. 生命周期管理（连接池、会话存储）
5. 后台任务（定期清理过期会话）
6. 限流中间件
7. 请求追踪 ID 中间件
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import dangbei_client
from app.errors import global_exception_handler
from app.logger import get_logger, setup_logging
from app.middleware import RequestIDMiddleware
from app.routes import limiter, router
from app.session_store import close_session_store, get_session_store
from app.settings import settings

# 配置日志
setup_logging()
logger = get_logger(__name__)


# 后台任务：定期清理过期会话
async def cleanup_expired_sessions_task():
    """后台任务：定期清理过期会话"""
    while True:
        try:
            await asyncio.sleep(settings.session_cleanup_interval)
            store = await get_session_store()
            cleaned = await store.cleanup_expired()
            if cleaned > 0:
                logger.info("后台清理任务完成", cleaned_count=cleaned)
        except asyncio.CancelledError:
            logger.info("后台清理任务已取消")
            break
        except Exception as e:
            logger.error("后台清理任务出错", error=str(e), exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(
        "Dangbei2API 启动中",
        version="0.2.1",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        session_store="sqlite" if settings.use_sqlite_session else "memory",
    )

    # 启动：初始化资源
    await dangbei_client.get_http_client()
    await get_session_store()

    # 启动后台清理任务
    cleanup_task = None
    if settings.session_expire_seconds > 0:
        cleanup_task = asyncio.create_task(cleanup_expired_sessions_task())
        logger.info(
            "后台清理任务已启动",
            interval=settings.session_cleanup_interval,
            expire_seconds=settings.session_expire_seconds,
        )

    yield

    # 关闭：清理资源
    logger.info("Dangbei2API 关闭中")

    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

    await dangbei_client.close_http_client()
    await close_session_store()

    logger.info("Dangbei2API 已关闭")


app = FastAPI(
    title="Dangbei2API",
    description="将当贝 AI (ai.dangbei.com) 网页版能力封装为 OpenAI 兼容 API",
    version="0.2.1",
    lifespan=lifespan,
)

# 请求追踪 ID 中间件（最先添加，确保所有请求都有追踪 ID）
app.add_middleware(RequestIDMiddleware)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流中间件
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 全局异常处理
app.add_exception_handler(Exception, global_exception_handler)

# 注册路由
app.include_router(router)


@app.get("/")
async def root():
    """根端点 - 服务信息"""
    return {
        "service": "Dangbei2API",
        "version": "0.2.1",
        "endpoints": {
            "/v1/chat/completions": "OpenAI chat completions (stream & non-stream)",
            "/v1/responses": "OpenAI Responses API (stream & non-stream)",
            "/v1/models": "List available models",
            "/v1/conversations": "Session management (list/delete)",
            "/health": "Health check",
        },
        "features": {
            "auth": "enabled" if settings.api_key else "disabled (set API_KEY to enable)",
            "session_store": "sqlite" if settings.use_sqlite_session else "memory",
            "rate_limit": f"{settings.rate_limit_per_minute}/min" if settings.rate_limit_enabled else "disabled",
            "anonymous_mode": not bool(settings.dangbei_token),
        },
    }


def main():
    """Entry point for `uv run dangbei2api`"""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,  # 生产环境建议关闭
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
