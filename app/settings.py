"""
配置管理 - 使用 pydantic-settings 统一配置。

支持从环境变量和 .env 文件加载配置。
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Dangbei API
    dangbei_base_url: str = Field(
        default="https://ai-api.dangbei.net",
        description="当贝 API 基础 URL"
    )
    dangbei_token: str = Field(
        default="",
        description="当贝登录 token（留空为匿名模式）"
    )

    # 服务器配置
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8000, description="监听端口")

    # 模型配置
    default_model: str = Field(default="deepseek-v3", description="默认模型")
    default_user_action: str = Field(
        default="online,deep",
        description="默认用户行为（无后缀模型时生效）"
    )

    # 鉴权配置
    api_key: str = Field(
        default="",
        description="API 鉴权密钥（留空则不校验）"
    )

    # 会话管理
    session_expire_seconds: int = Field(
        default=1800,
        description="会话过期时间（秒），0 表示永不过期"
    )
    session_cleanup_interval: int = Field(
        default=300,
        description="会话清理任务间隔（秒）"
    )
    use_sqlite_session: bool = Field(
        default=False,
        description="是否使用 SQLite 存储会话（默认使用内存）"
    )
    sqlite_db_path: str = Field(
        default="data/sessions.db",
        description="SQLite 数据库文件路径"
    )

    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_json: bool = Field(default=False, description="是否输出 JSON 格式日志")

    # 限流配置
    rate_limit_enabled: bool = Field(default=True, description="是否启用限流")
    rate_limit_per_minute: int = Field(default=60, description="每分钟请求限制")

    # 性能配置
    http_timeout: int = Field(default=300, description="HTTP 请求超时时间（秒）")
    http_max_connections: int = Field(default=100, description="HTTP 最大连接数")
    http_max_keepalive: int = Field(default=20, description="HTTP 最大保持连接数")

    # 缓存配置
    model_cache_ttl: int = Field(default=3600, description="模型列表缓存时间（秒）")

    # 当贝 API 请求头
    @property
    def base_headers(self) -> dict:
        """基础请求头"""
        return {
            "content-type": "application/json",
            "lang": "zh",
            "apptype": "6",
            "appversion": "1.3.9",
            "client-ver": "1.0.2",
            "Origin": "https://ai.dangbei.com",
            "Referer": "https://ai.dangbei.com/",
        }


# 全局配置实例
settings = Settings()
