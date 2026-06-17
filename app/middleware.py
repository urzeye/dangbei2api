"""
请求追踪中间件 - 为每个请求生成唯一的追踪 ID。
"""

import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logger import get_logger

logger = get_logger(__name__)

# 上下文变量：存储当前请求的追踪 ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """获取当前请求的追踪 ID"""
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    请求追踪 ID 中间件。

    功能：
    1. 为每个请求生成或复用 X-Request-ID
    2. 将追踪 ID 注入到日志上下文
    3. 在响应头中返回追踪 ID
    """

    async def dispatch(self, request: Request, call_next):
        # 1. 从请求头获取或生成追踪 ID
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        request_id_var.set(request_id)

        # 2. 记录请求开始（带追踪 ID）
        logger.info(
            "请求开始",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        # 3. 处理请求
        try:
            response: Response = await call_next(request)
        except Exception as e:
            logger.error(
                "请求处理异常",
                request_id=request_id,
                exc_type=type(e).__name__,
                exc_msg=str(e),
                exc_info=True,
            )
            raise
        finally:
            # 清理上下文
            request_id_var.set("")

        # 4. 添加追踪 ID 到响应头
        response.headers["X-Request-ID"] = request_id

        # 5. 记录请求完成
        logger.info(
            "请求完成",
            request_id=request_id,
            status_code=response.status_code,
        )

        return response
