import os
from dotenv import load_dotenv

load_dotenv()

DANGBEI_BASE_URL = os.getenv("DANGBEI_BASE_URL", "https://ai-api.dangbei.net")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek-v3")
DANGBEI_TOKEN = os.getenv("DANGBEI_TOKEN", "")  # empty = anonymous mode

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
