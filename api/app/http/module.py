from flask_migrate import Migrate
from injector import Module, Binder, singleton
from internal.extension.database_extension import db
from internal.extension.migrate_extension import migrate
from flask_weaviate import FlaskWeaviate
from internal.extension.redis_extension import redis_client
from pkg.sqlalchemy import SQLAlchemy
from redis import Redis
from injector import Injector
from flask_login import LoginManager
from internal.extension.login_extension import login_manager
from internal.extension.weaviate_extension import weaviate
from internal.extension.mail_extension import mail
from flask_mail import Mail
from internal.core.language_model import LanguageModelManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.service.notification_service import NotificationService


class ExtensionModule(Module):
    """扩展模块的依赖注入"""

    def configure(self, binder: Binder) -> None:
        binder.bind(SQLAlchemy, to=db, scope=singleton)
        binder.bind(FlaskWeaviate, to=weaviate, scope=singleton)
        binder.bind(Migrate, to=migrate, scope=singleton)
        binder.bind(Redis, to=redis_client, scope=singleton)
        binder.bind(LoginManager, to=login_manager, scope=singleton)
        binder.bind(Mail, to=mail, scope=singleton)

        # 注册核心管理器类为单例
        binder.bind(LanguageModelManager, to=LanguageModelManager, scope=singleton)
        binder.bind(BuiltinProviderManager, to=BuiltinProviderManager, scope=singleton)
        binder.bind(ApiProviderManager, to=ApiProviderManager, scope=singleton)

        # 注册服务类为单例
        binder.bind(NotificationService, to=NotificationService, scope=singleton)

injector = Injector([ExtensionModule])
