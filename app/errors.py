"""
统一错误处理 - OpenAI 兼容错误格式。

参考：https://platform.openai.com/docs/guides/error-codes
"""

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.logger import get_logger

logger = get_logger(__name__)


class DangbeiAPIError(Exception):
    """当贝 API 错误"""

    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class OpenAIErrorResponse:
    """OpenAI 格式错误响应"""

    @staticmethod
    def format_error(
        message: str,
        type: str = "invalid_request_error",
        param: str | None = None,
        code: str | None = None,
    ) -> dict[str, Any]:
        """构造 OpenAI 格式错误响应"""
        error = {
            "message": message,
            "type": type,
        }
        if param:
            error["param"] = param
        if code:
            error["code"] = code
        return {"error": error}


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器"""

    # 记录异常
    logger.error(
        "请求处理异常",
        exc_type=type(exc).__name__,
        exc_msg=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True,
    )

    # HTTPException - FastAPI 标准异常
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=OpenAIErrorResponse.format_error(
                message=exc.detail,
                type="invalid_request_error" if exc.status_code < 500 else "server_error",
            ),
        )

    # DangbeiAPIError - 当贝 API 错误
    if isinstance(exc, DangbeiAPIError):
        return JSONResponse(
            status_code=exc.status_code,
            content=OpenAIErrorResponse.format_error(
                message=f"当贝 API 错误: {exc.message}",
                type="api_error",
                code="dangbei_error",
            ),
        )

    # 未知异常
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=OpenAIErrorResponse.format_error(
            message="服务器内部错误",
            type="server_error",
            code="internal_error",
        ),
    )


def validate_request(condition: bool, message: str, param: str | None = None):
    """验证请求参数，不满足条件时抛出 400 错误"""
    if not condition:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=OpenAIErrorResponse.format_error(
                message=message,
                type="invalid_request_error",
                param=param,
            )["error"]["message"],
        )
