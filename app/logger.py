"""
结构化日志配置 - 使用 structlog。

提供统一的日志接口，支持 JSON 和人类可读格式。
"""

import logging
import sys

import structlog

from app.settings import settings


def setup_logging():
    """配置结构化日志"""

    # 配置标准库 logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    # 配置 structlog 处理器
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_json:
        # JSON 格式（生产环境）
        processors.append(structlog.processors.JSONRenderer())
    else:
        # 人类可读格式（开发环境）
        processors.extend([
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.dev.ConsoleRenderer(colors=True),
        ])

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__):
    """获取结构化日志记录器"""
    return structlog.get_logger(name)
