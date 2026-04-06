import os
from typing import Any
from kombu import Queue
from .default_config import DEFAULT_CONFIG


def _get_env(key: str) -> Any:
    """从环境变量中获取配置项，如果找不到则返回默认值"""
    return os.getenv(key, DEFAULT_CONFIG.get(key))


def _get_bool_env(key: str) -> bool:
    """从环境变量中获取布尔值型的配置项，如果找不到则返回默认值"""
    value = _get_env(key)
    if value is None:
        return False

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return False


def _get_list_env(key: str) -> list[str]:
    """从环境变量中获取字符串列表配置，逗号分隔。"""
    value = _get_env(key)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _build_redis_auth(username: Any, password: Any) -> str:
    """构建 Redis 认证片段，兼容空用户名或空密码。"""
    redis_username = str(username or "")
    redis_password = str(password or "")

    if redis_username and redis_password:
        return f"{redis_username}:{redis_password}@"
    if redis_username:
        return f"{redis_username}@"
    if redis_password:
        return f":{redis_password}@"
    return ""


def _build_redis_url(*, host: Any, port: Any, db: Any, use_ssl: bool, username: Any, password: Any) -> str:
    """统一构建 Redis 连接 URL。"""
    protocol = "rediss" if use_ssl else "redis"
    auth = _build_redis_auth(username, password)
    return f"{protocol}://{auth}{host}:{port}/{db}"


class Config:
    def __init__(self):
        # 关闭wtf的csrf保护
        self.WTF_CSRF_ENABLED = _get_bool_env("WTF_CSRF_ENABLED")
        self.CORS_ALLOW_ORIGINS = _get_list_env("CORS_ALLOW_ORIGINS")
        self.CORS_SUPPORTS_CREDENTIALS = _get_bool_env("CORS_SUPPORTS_CREDENTIALS")
        self.OAUTH_ALLOWED_ORIGINS = _get_list_env("OAUTH_ALLOWED_ORIGINS")
        self.WEB_APP_VISITOR_COOKIE_SECURE = _get_bool_env("WEB_APP_VISITOR_COOKIE_SECURE")
        self.WEB_APP_VISITOR_COOKIE_SECRET = _get_env("WEB_APP_VISITOR_COOKIE_SECRET")

        # SQLAlchemy数据库配置
        self.SQLALCHEMY_DATABASE_URI = _get_env("SQLALCHEMY_DATABASE_URI")
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": int(_get_env("SQLALCHEMY_POOL_SIZE")),
            "pool_recycle": int(_get_env("SQLALCHEMY_POOL_RECYCLE")),
        }
        # 强制数据库会话使用UTC，避免CURRENT_TIMESTAMP受连接时区影响
        if self.SQLALCHEMY_DATABASE_URI and self.SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
            self.SQLALCHEMY_ENGINE_OPTIONS["connect_args"] = {
                "options": "-c timezone=UTC"
            }
        self.SQLALCHEMY_ECHO = _get_bool_env("SQLALCHEMY_ECHO")

        # Weaviate向量数据库配置
        self.WEAVIATE_HTTP_HOST = _get_env("WEAVIATE_HTTP_HOST")
        self.WEAVIATE_HTTP_PORT = _get_env("WEAVIATE_HTTP_PORT")
        self.WEAVIATE_GRPC_HOST = _get_env("WEAVIATE_GRPC_HOST")
        self.WEAVIATE_GRPC_PORT = _get_env("WEAVIATE_GRPC_PORT")
        # API Key must come from environment/.env only, no default fallback.
        self.WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

        # Redis配置
        self.REDIS_HOST = _get_env("REDIS_HOST")
        self.REDIS_PORT = _get_env("REDIS_PORT")
        self.REDIS_USERNAME = _get_env("REDIS_USERNAME")
        self.REDIS_PASSWORD = _get_env("REDIS_PASSWORD")
        self.REDIS_DB = _get_env("REDIS_DB")
        self.REDIS_USE_SSL = _get_bool_env("REDIS_USE_SSL")

        # 构建 Redis URL
        self.REDIS_URL = _build_redis_url(
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            db=self.REDIS_DB,
            use_ssl=self.REDIS_USE_SSL,
            username=self.REDIS_USERNAME,
            password=self.REDIS_PASSWORD,
        )

        # Celery配置
        self.CELERY = {
            "broker_url": _build_redis_url(
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                db=int(_get_env("CELERY_BROKER_DB")),
                use_ssl=self.REDIS_USE_SSL,
                username=self.REDIS_USERNAME,
                password=self.REDIS_PASSWORD,
            ),
            "result_backend": _build_redis_url(
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                db=int(_get_env("CELERY_RESULT_BACKEND_DB")),
                use_ssl=self.REDIS_USE_SSL,
                username=self.REDIS_USERNAME,
                password=self.REDIS_PASSWORD,
            ),
            "task_ignore_result": _get_bool_env("CELERY_TASK_IGNORE_RESULT"),
            "result_expires": int(_get_env("CELERY_RESULT_EXPIRES")),
            "broker_connection_retry_on_startup": _get_bool_env("CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP"),
            "task_default_queue": "celery",
            "task_queues": (
                Queue("celery"),
                Queue("mail"),
            ),
            "task_routes": {
                "internal.task.email_task.send_verification_email_task": {"queue": "mail"},
            },
        }

        # 辅助Agent应用id标识
        self.ASSISTANT_AGENT_ID = _get_env("ASSISTANT_AGENT_ID")

        # 图标生成服务 API Key
        self.SILICONFLOW_API_KEY = _get_env("SILICONFLOW_API_KEY")
        self.DASHSCOPE_API_KEY = _get_env("DASHSCOPE_API_KEY")
        self.OPENAI_API_KEY = _get_env("OPENAI_API_KEY")

        # COS 配置
        self.COS_SECRET_ID = _get_env("COS_SECRET_ID")
        self.COS_SECRET_KEY = _get_env("COS_SECRET_KEY")
        self.COS_BUCKET = _get_env("COS_BUCKET")
        self.COS_REGION = _get_env("COS_REGION")
        self.COS_DOMAIN = _get_env("COS_DOMAIN")

        # Flask-Mail 邮件服务配置
        self.MAIL_SERVER = _get_env("MAIL_SERVER")
        self.MAIL_PORT = int(_get_env("MAIL_PORT")) if _get_env("MAIL_PORT") else 587
        self.MAIL_USE_TLS = _get_bool_env("MAIL_USE_TLS")
        self.MAIL_USE_SSL = _get_bool_env("MAIL_USE_SSL")
        self.MAIL_USERNAME = _get_env("MAIL_USERNAME")
        self.MAIL_PASSWORD = _get_env("MAIL_PASSWORD")
        self.MAIL_DEFAULT_SENDER = _get_env("MAIL_DEFAULT_SENDER")
        self.MAIL_TIMEOUT = int(_get_env("MAIL_TIMEOUT"))
