"""
工具函数模块 - 消除重复代码。
"""

from app.models import Message
from app.settings import settings


def extract_user_question(messages: list[Message]) -> str:
    """从 messages 数组中提取最后一条 user 消息的文本内容"""
    for m in reversed(messages):
        if m.role == "user" and isinstance(m.content, str):
            return m.content
    return ""


def parse_model_and_action(model: str) -> tuple[str, str]:
    """
    从模型名解析出实际当贝模型名和 userAction。

    示例：
        - deepseek-v3-online-deep → ("deepseek-v3", "online,deep")
        - deepseek-v3-online → ("deepseek-v3", "online")
        - deepseek-v3-deep → ("deepseek-v3", "deep")
        - deepseek-v3-basic → ("deepseek-v3", "")
        - deepseek-v3 → ("deepseek-v3", "online,deep")  # 默认
    """
    known_suffixes = ["-online-deep", "-deep-online", "-online", "-deep", "-basic"]

    for suffix in known_suffixes:
        if model.endswith(suffix):
            base = model[: -len(suffix)]
            action = suffix[1:]  # 去掉前导 "-"

            # 标准化 action
            if action in ("deep-online", "online-deep"):
                action = "online,deep"
            elif action == "basic":
                action = ""

            return base, action

    # 无已知后缀 → 使用默认行为
    return model, settings.default_user_action
