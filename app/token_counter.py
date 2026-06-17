"""
Token 计算工具 - 使用 tiktoken 精确计算 token 数量。
"""

import tiktoken
from functools import lru_cache

from app.logger import get_logger

logger = get_logger(__name__)


# 模型 ID 到 tiktoken 编码器映射
MODEL_ENCODING_MAP = {
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "text-embedding-ada-002": "cl100k_base",
    # 通用编码器（默认）
    "default": "cl100k_base",
}


@lru_cache(maxsize=10)
def get_encoding(model: str = "default") -> tiktoken.Encoding:
    """
    获取指定模型的 tiktoken 编码器（带缓存）。

    对于当贝模型，使用 cl100k_base 编码器作为通用估算。
    """
    encoding_name = MODEL_ENCODING_MAP.get(model, MODEL_ENCODING_MAP["default"])
    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception as e:
        logger.warning("获取 tiktoken 编码器失败，使用默认", model=model, error=str(e))
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "default") -> int:
    """
    计算文本的 token 数量。

    Args:
        text: 待计算的文本
        model: 模型名称（用于选择编码器）

    Returns:
        token 数量
    """
    if not text:
        return 0

    try:
        encoding = get_encoding(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning("Token 计算失败，使用字符估算", error=str(e))
        # 降级到字符估算（中文约 1.5 字符/token，英文约 4 字符/token）
        # 使用保守估计：平均 2 字符/token
        return max(1, len(text) // 2)


def estimate_prompt_tokens(completion_tokens: int) -> int:
    """
    根据补全 token 数估算 prompt token 数。

    经验规则：prompt 通常是 completion 的 1-3 倍
    使用保守估计 1.5 倍
    """
    return max(1, int(completion_tokens * 1.5))
