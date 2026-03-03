# 应用默认配置项
DEFAULT_CONFIG = {
    # wft配置
    "WTF_CSRF_ENABLED": "True",
    # CORS 配置
    "CORS_ALLOW_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
    "CORS_SUPPORTS_CREDENTIALS": "True",
    # OAuth 回调来源白名单（逗号分隔）
    "OAUTH_ALLOWED_ORIGINS": "",
    # WebApp 访客 Cookie 配置
    "WEB_APP_VISITOR_COOKIE_SECURE": "False",
    "WEB_APP_VISITOR_COOKIE_SECRET": "",
    
    # SQLAlchemy数据库配置
    "SQLALCHEMY_DATABASE_URI": "",
    "SQLALCHEMY_POOL_SIZE": 30,
    "SQLALCHEMY_POOL_RECYCLE": 3600,
    "SQLALCHEMY_ECHO": "True",

    # Weaviate向量数据库配置
    "WEAVIATE_HTTP_HOST": "localhost",
    "WEAVIATE_HTTP_PORT": 8080,
    "WEAVIATE_GRPC_HOST": "localhost",
    "WEAVIATE_GRPC_PORT": 50051,

    # Redis数据库配置
    "REDIS_HOST": "localhost",
    "REDIS_PORT": 6379,
    "REDIS_USERNAME": "",
    "REDIS_PASSWORD": "",
    "REDIS_DB": 0,
    "REDIS_USE_SSL": "False",

    # Celery默认配置
    "CELERY_BROKER_DB": 1,
    "CELERY_RESULT_BACKEND_DB": 1,
    "CELERY_TASK_IGNORE_RESULT": "False",
    "CELERY_RESULT_EXPIRES": 3600,
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP": "True",

    # 辅助Agent智能体应用id
    "ASSISTANT_AGENT_ID": "6774fcef-b594-8008-b30c-a05b8190afe6",

    # Flask-Mail 邮件服务默认配置
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 587,
    "MAIL_USE_TLS": "True",
    "MAIL_USE_SSL": "False",
    "MAIL_USERNAME": "",
    "MAIL_PASSWORD": "",
    "MAIL_DEFAULT_SENDER": "",
}
