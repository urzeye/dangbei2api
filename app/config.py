import os
from dotenv import load_dotenv

load_dotenv()

DANGBEI_BASE_URL = os.getenv("DANGBEI_BASE_URL", "https://ai-api.dangbei.net")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek-v3")
DANGBEI_TOKEN = os.getenv("DANGBEI_TOKEN", "")  # empty = anonymous mode

# API Key 鉴权（可选，留空则不校验）
# 设置后客户端必须带 Authorization: Bearer <API_KEY> 才能访问
API_KEY = os.getenv("API_KEY", "")

# 默认开启联网搜索 + 深度思考（模型支持时自动生效）
DEFAULT_USER_ACTION = os.getenv("DEFAULT_USER_ACTION", "online,deep")

# 会话过期时间（秒），0 表示永不过期
SESSION_EXPIRE_SECONDS = int(os.getenv("SESSION_EXPIRE_SECONDS", "1800"))  # 默认 30 分钟

# 当贝模型名 → userAction 后缀映射
# 客户端通过模型名后缀控制行为：
#   deepseek-v3            → 纯对话
#   deepseek-v3-online     → 联网搜索
#   deepseek-v3-deep       → 深度思考
#   deepseek-v3-online-deep → 联网 + 深度思考
MODEL_ACTION_MAP = {
    "online": "online",
    "deep": "deep",
}

# Common headers for Dangbei API
BASE_HEADERS = {
    "content-type": "application/json",
    "lang": "zh",
    "apptype": "6",
    "appversion": "1.3.9",
    "client-ver": "1.0.2",
    "Origin": "https://ai.dangbei.com",
    "Referer": "https://ai.dangbei.com/",
}
