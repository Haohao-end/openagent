from types import SimpleNamespace
from uuid import UUID
from uuid import uuid4
from injector import inject
from dataclasses import dataclass
import os
from itsdangerous import URLSafeSerializer, BadSignature
from internal.service import WebAppService
from flask_login import current_user
from internal.schema.web_app_schema import (
    GetWebAppResp,
    WebAppChatReq,
    GetConversationsResp,
    GetConversationsReq
)
from flask import request, current_app
from pkg.response import success_json, success_message, validate_error_json, compact_generate_response


@inject
@dataclass
class WebAppHandler:
    """WebApp处理器"""
    web_app_service: WebAppService
    VISITOR_COOKIE_KEY = "llmops_webapp_visitor_id"
    VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
    VISITOR_COOKIE_SIGN_SALT = "llmops-webapp-visitor-cookie"

    @classmethod
    def _is_authenticated_user(cls) -> bool:
        try:
            return bool(getattr(current_user, "is_authenticated", False))
        except Exception:
            return False

    @classmethod
    def _get_visitor_cookie_signer(cls) -> URLSafeSerializer | None:
        cookie_secret = (
            current_app.config.get("WEB_APP_VISITOR_COOKIE_SECRET")
            or current_app.config.get("SECRET_KEY")
            or os.getenv("JWT_SECRET_KEY")
            or ""
        )
        cookie_secret = str(cookie_secret).strip()
        if cookie_secret == "":
            return None
        return URLSafeSerializer(cookie_secret, salt=cls.VISITOR_COOKIE_SIGN_SALT)

    @classmethod
    def _decode_visitor_cookie(cls, raw_visitor_cookie: str) -> UUID | None:
        if raw_visitor_cookie == "":
            return None

        signer = cls._get_visitor_cookie_signer()
        try:
            decoded_visitor_id = signer.loads(raw_visitor_cookie) if signer else raw_visitor_cookie
            return UUID(str(decoded_visitor_id))
        except (BadSignature, TypeError, ValueError):
            return None

    @classmethod
    def _encode_visitor_cookie(cls, visitor_id: UUID) -> str:
        signer = cls._get_visitor_cookie_signer()
        raw_visitor_id = str(visitor_id)
        if signer:
            return signer.dumps(raw_visitor_id)
        return raw_visitor_id

    @classmethod
    def _resolve_web_app_actor(cls) -> tuple[object, str | None]:
        """解析 WebApp 会话主体：已登录用户优先，未登录用户使用访客 cookie。"""
        if cls._is_authenticated_user():
            return current_user, None

        raw_visitor_cookie = (request.cookies.get(cls.VISITOR_COOKIE_KEY) or "").strip()
        visitor_id = cls._decode_visitor_cookie(raw_visitor_cookie)
        if visitor_id:
            return SimpleNamespace(id=visitor_id, is_authenticated=False), None

        visitor_id = uuid4()
        visitor_cookie = cls._encode_visitor_cookie(visitor_id)
        return SimpleNamespace(id=visitor_id, is_authenticated=False), visitor_cookie

    @classmethod
    def _attach_visitor_cookie(cls, response, visitor_cookie: str | None):
        if not visitor_cookie:
            return response

        response_obj = response[0] if isinstance(response, tuple) else response
        secure_cookie = bool(current_app.config.get("WEB_APP_VISITOR_COOKIE_SECURE", False))
        response_obj.set_cookie(
            cls.VISITOR_COOKIE_KEY,
            visitor_cookie,
            max_age=cls.VISITOR_COOKIE_MAX_AGE,
            httponly=True,
            secure=secure_cookie,
            samesite="Lax",
            path="/",
        )
        return response

    def get_web_app(self, token: str):
        """根据传递的token凭证标识获取WebApp基础信息"""
        _, visitor_cookie = self._resolve_web_app_actor()

        # 1.调用服务根据传递的token获取应用信息
        resp = self.web_app_service.get_web_app_info(token)

        # 2.返回成功响应
        return self._attach_visitor_cookie(success_json(resp), visitor_cookie)

    def web_app_chat(self, token: str):
        """根据传递的token+query等信息与WebApp进行对话"""
        actor, visitor_cookie = self._resolve_web_app_actor()

        # 1.提取信息并校验
        req = WebAppChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取对应响应内容
        response = self.web_app_service.web_app_chat(token, req, actor)

        return self._attach_visitor_cookie(compact_generate_response(response), visitor_cookie)

    def stop_web_app_chat(self, token: str, task_id: UUID):
        """根据传递的token+task_id停止与WebApp的对话"""
        actor, visitor_cookie = self._resolve_web_app_actor()
        self.web_app_service.stop_web_app_chat(token, task_id, actor)
        return self._attach_visitor_cookie(success_message("停止WebApp会话成功"), visitor_cookie)

    def get_conversations(self, token: str):
        """根据传递的token+is_pinned获取指定WebApp下的所有会话列表信息"""
        actor, visitor_cookie = self._resolve_web_app_actor()

        # 1.提取请求并校验
        req = GetConversationsReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取会话列表
        conversation = self.web_app_service.get_conversations(
            token,
            req.is_pinned.data,
            actor,
            req.current_page.data,
            req.page_size.data,
        )

        # 3.构建响应并返回
        resp = GetConversationsResp(many=True)

        return self._attach_visitor_cookie(success_json(resp.dump(conversation)), visitor_cookie)


