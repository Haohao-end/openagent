from dataclasses import dataclass
from flask import Flask, Blueprint
from injector import inject

from internal.handler import (
    AppHandler,
    BuiltinToolHandler,
    ApiToolHandler,
    UploadFileHandler,
    DatasetHandler,
    DocumentHandler,
    SegmentHandler,
    OAuthHandler,
    AccountHandler,
    AuthHandler,
    AIHandler,
    ApiKeyHandler,
    OpenAPIHandler,
    WorkflowHandler,
    LanguageModelHandler,
    AssistantAgentHandler,
    AnalysisHandler,
    WebAppHandler,
    ConversationHandler,
    AudioHandler,
    PlatformHandler,
    WechatHandler,
    PublicAppHandler,
    PublicWorkflowHandler,
    HomeHandler,
    NotificationHandler

)


@inject
@dataclass
class Router:
    """路由"""
    app_handler: AppHandler
    builtin_tool_handler: BuiltinToolHandler
    api_tool_handler: ApiToolHandler
    upload_file_handler: UploadFileHandler
    dataset_handler: DatasetHandler
    document_handler: DocumentHandler
    segment_handler: SegmentHandler
    oauth_handler: OAuthHandler
    account_handler: AccountHandler
    auth_handler: AuthHandler
    ai_handler: AIHandler
    api_key_handler: ApiKeyHandler
    openapi_handler: OpenAPIHandler
    workflow_handler: WorkflowHandler
    language_model_handler: LanguageModelHandler
    assistant_agent_handler: AssistantAgentHandler
    analysis_handler: AnalysisHandler
    web_app_handler: WebAppHandler
    conversation_handler: ConversationHandler
    audio_handler: AudioHandler
    platform_handler: PlatformHandler
    wechat_handler: WechatHandler
    public_app_handler: PublicAppHandler
    public_workflow_handler: PublicWorkflowHandler
    home_handler: HomeHandler
    notification_handler: NotificationHandler

    def register_router(self, app: Flask):
        """注册路由"""
        # 1.创建一个蓝图
        bp = Blueprint("llmops", __name__, url_prefix="")
        openapi_bp = Blueprint("openapi", __name__, url_prefix="")

        # 2.将url与对应的控制器方法做绑定
        bp.add_url_rule("/health", view_func=self.app_handler.health)
        bp.add_url_rule("/ping", view_func=self.app_handler.ping)
        bp.add_url_rule("/apps", view_func=self.app_handler.get_apps_with_page)
        bp.add_url_rule("/apps", methods=["POST"], view_func=self.app_handler.create_app)
        bp.add_url_rule("/apps/<uuid:app_id>", view_func=self.app_handler.get_app)
        bp.add_url_rule("/apps/<uuid:app_id>", methods=["POST"], view_func=self.app_handler.update_app)
        bp.add_url_rule("/apps/<uuid:app_id>/delete", methods=["POST"], view_func=self.app_handler.delete_app)
        bp.add_url_rule("/apps/<uuid:app_id>/copy", methods=["POST"], view_func=self.app_handler.copy_app)
        bp.add_url_rule("/apps/<uuid:app_id>/draft-app-config", view_func=self.app_handler.get_draft_app_config)
        bp.add_url_rule(
            "/apps/<uuid:app_id>/draft-app-config",
            methods=["POST"],
            view_func=self.app_handler.update_draft_app_config,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/publish",
            methods=["POST"],
            view_func=self.app_handler.publish,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/cancel-publish",
            methods=["POST"],
            view_func=self.app_handler.cancel_publish,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/publish-histories",
            view_func=self.app_handler.get_publish_histories_with_page,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/fallback-history",
            methods=["POST"],
            view_func=self.app_handler.fallback_history_to_draft,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/summary",
            view_func=self.app_handler.get_debug_conversation_summary,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/summary",
            methods=["POST"],
            view_func=self.app_handler.update_debug_conversation_summary,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/conversations/delete-debug-conversation",
            methods=["POST"],
            view_func=self.app_handler.delete_debug_conversation,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/conversations",
            methods=["POST"],
            view_func=self.app_handler.debug_chat,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/conversations/tasks/<uuid:task_id>/stop",
            methods=["POST"],
            view_func=self.app_handler.stop_debug_chat,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/conversations/messages",
            view_func=self.app_handler.get_debug_conversation_messages_with_page,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/published-config",
            view_func=self.app_handler.get_published_config,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/published-config/regenerate-web-app-token",
            methods=["POST"],
            view_func=self.app_handler.regenerate_web_app_token,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/regenerate-icon",
            methods=["POST"],
            view_func=self.app_handler.regenerate_icon,
            endpoint="app_regenerate_icon",
        )
        bp.add_url_rule(
            "/apps/generate-icon-preview",
            methods=["POST"],
            view_func=self.app_handler.generate_icon_preview,
            endpoint="app_generate_icon_preview",
        )

        # 3.内置插件广场模块
        bp.add_url_rule("/builtin-tools", view_func=self.builtin_tool_handler.get_builtin_tools)
        bp.add_url_rule(
            "/builtin-tools/<string:provider_name>/tools/<string:tool_name>",
            view_func=self.builtin_tool_handler.get_provider_tool,
        )
        bp.add_url_rule(
            "/builtin-tools/<string:provider_name>/icon",
            view_func=self.builtin_tool_handler.get_provider_icon,
        )
        bp.add_url_rule(
            "/builtin-tools/categories",
            view_func=self.builtin_tool_handler.get_categories,
        )

        # 4.自定义API插件模块
        bp.add_url_rule(
            "/api-tools",
            view_func=self.api_tool_handler.get_api_tool_providers_with_page,
        )
        bp.add_url_rule(
            "/api-tools/validate-openapi-schema",
            methods=["POST"],
            view_func=self.api_tool_handler.validate_openapi_schema,
        )
        bp.add_url_rule(
            "/api-tools",
            methods=["POST"],
            view_func=self.api_tool_handler.create_api_tool_provider,
        )
        bp.add_url_rule(
            "/api-tools/<uuid:provider_id>",
            view_func=self.api_tool_handler.get_api_tool_provider,
        )
        bp.add_url_rule(
            "/api-tools/<uuid:provider_id>",
            methods=["POST"],
            view_func=self.api_tool_handler.update_api_tool_provider,
        )
        bp.add_url_rule(
            "/api-tools/<uuid:provider_id>/tools/<string:tool_name>",
            view_func=self.api_tool_handler.get_api_tool,
        )
        bp.add_url_rule(
            "/api-tools/<uuid:provider_id>/delete",
            methods=["POST"],
            view_func=self.api_tool_handler.delete_api_tool_provider,
        )
        bp.add_url_rule(
            "/api-tools/<uuid:provider_id>/regenerate-icon",
            methods=["POST"],
            view_func=self.api_tool_handler.regenerate_icon,
            endpoint="api_tool_regenerate_icon",
        )
        bp.add_url_rule(
            "/api-tools/generate-icon-preview",
            methods=["POST"],
            view_func=self.api_tool_handler.generate_icon_preview,
            endpoint="api_tool_generate_icon_preview",
        )

        # 4.上传文件模块
        bp.add_url_rule("/upload-files/file", methods=["POST"], view_func=self.upload_file_handler.upload_file)
        bp.add_url_rule("/upload-files/image", methods=["POST"], view_func=self.upload_file_handler.upload_image)

        # 5.知识库模块
        bp.add_url_rule("/datasets", view_func=self.dataset_handler.get_datasets_with_page)
        bp.add_url_rule("/datasets", methods=["POST"], view_func=self.dataset_handler.create_dataset)
        bp.add_url_rule("/datasets/<uuid:dataset_id>", view_func=self.dataset_handler.get_dataset)
        bp.add_url_rule("/datasets/<uuid:dataset_id>", methods=["POST"], view_func=self.dataset_handler.update_dataset)
        bp.add_url_rule("/datasets/<uuid:dataset_id>/queries", view_func=self.dataset_handler.get_dataset_queries)
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/delete",
            methods=["POST"],
            view_func=self.dataset_handler.delete_dataset,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents",
            view_func=self.document_handler.get_documents_with_page,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents",
            methods=["POST"],
            view_func=self.document_handler.create_documents,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>",
            view_func=self.document_handler.get_document,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/name",
            methods=["POST"],
            view_func=self.document_handler.update_document_name,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/enabled",
            methods=["POST"],
            view_func=self.document_handler.update_document_enabled,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/delete",
            methods=["POST"],
            view_func=self.document_handler.delete_document,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/batch/<string:batch>",
            view_func=self.document_handler.get_documents_status,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments",
            view_func=self.segment_handler.get_segments_with_page,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments",
            methods=["POST"],
            view_func=self.segment_handler.create_segment,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments/<uuid:segment_id>",
            view_func=self.segment_handler.get_segment,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments/<uuid:segment_id>",
            methods=["POST"],
            view_func=self.segment_handler.update_segment,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments/<uuid:segment_id>/enabled",
            methods=["POST"],
            view_func=self.segment_handler.update_segment_enabled,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/documents/<uuid:document_id>/segments/<uuid:segment_id>/delete",
            methods=["POST"],
            view_func=self.segment_handler.delete_segment,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/hit",
            methods=["POST"],
            view_func=self.dataset_handler.hit,
        )
        bp.add_url_rule(
            "/datasets/<uuid:dataset_id>/regenerate-icon",
            methods=["POST"],
            view_func=self.dataset_handler.regenerate_icon,
            endpoint="dataset_regenerate_icon",
        )
        bp.add_url_rule(
            "/datasets/generate-icon-preview",
            methods=["POST"],
            view_func=self.dataset_handler.generate_icon_preview,
            endpoint="dataset_generate_icon_preview",
        )

        # 6.授权认证模块
        bp.add_url_rule(
            "/oauth/<string:provider_name>",
            view_func=self.oauth_handler.provider,
        )
        bp.add_url_rule(
            "/oauth/authorize/<string:provider_name>",
            methods=["POST"],
            view_func=self.oauth_handler.authorize,
        )
        bp.add_url_rule(
            "/auth/password-login",
            methods=["POST"],
            view_func=self.auth_handler.password_login,
        )
        bp.add_url_rule(
            "/auth/logout",
            methods=["POST"],
            view_func=self.auth_handler.logout,
        )
        bp.add_url_rule(
            "/auth/send-reset-code",
            methods=["POST"],
            view_func=self.auth_handler.send_reset_code,
        )
        bp.add_url_rule(
            "/auth/reset-password",
            methods=["POST"],
            view_func=self.auth_handler.reset_password,
        )

        # 7.账号设置模块
        bp.add_url_rule("/account", view_func=self.account_handler.get_current_user)
        bp.add_url_rule("/account/password", methods=["POST"], view_func=self.account_handler.update_password)
        bp.add_url_rule("/account/name", methods=["POST"], view_func=self.account_handler.update_name)
        bp.add_url_rule("/account/avatar", methods=["POST"], view_func=self.account_handler.update_avatar)

        # 7.1 首页模块
        bp.add_url_rule("/home/intent", view_func=self.home_handler.get_intent)

        # 8.AI辅助模块
        bp.add_url_rule("/ai/optimize-prompt", methods=["POST"], view_func=self.ai_handler.optimize_prompt)
        bp.add_url_rule(
            "/ai/suggested-questions",
            methods=["POST"],
            view_func=self.ai_handler.generate_suggested_questions
        )
        bp.add_url_rule("/ai/chat", methods=["POST"], view_func=self.ai_handler.code_assistant_chat)
        bp.add_url_rule(
            "/ai/openapi-schema-chat",
            methods=["POST"],
            view_func=self.ai_handler.openapi_schema_assistant_chat,
        )

        # 9.API秘钥模块
        bp.add_url_rule("/openapi/api-keys", view_func=self.api_key_handler.get_api_keys_with_page)
        bp.add_url_rule(
            "/openapi/api-keys",
            methods=["POST"],
            view_func=self.api_key_handler.create_api_key,
        )
        bp.add_url_rule(
            "/openapi/api-keys/<uuid:api_key_id>",
            methods=["POST"],
            view_func=self.api_key_handler.update_api_key,
        )
        bp.add_url_rule(
            "/openapi/api-keys/<uuid:api_key_id>/is-active",
            methods=["POST"],
            view_func=self.api_key_handler.update_api_key_is_active,
        )
        bp.add_url_rule(
            "/openapi/api-keys/<uuid:api_key_id>/delete",
            methods=["POST"],
            view_func=self.api_key_handler.delete_api_key,
        )
        openapi_bp.add_url_rule(
            "/openapi/chat",
            methods=["POST"],
            view_func=self.openapi_handler.chat,
        )

        # 10.工作流模块
        bp.add_url_rule("/workflows", view_func=self.workflow_handler.get_workflows_with_page)
        bp.add_url_rule("/workflows", methods=["POST"], view_func=self.workflow_handler.create_workflow)
        bp.add_url_rule("/workflows/<uuid:workflow_id>", view_func=self.workflow_handler.get_workflow)
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>",
            methods=["POST"],
            view_func=self.workflow_handler.update_workflow,
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/delete",
            methods=["POST"],
            view_func=self.workflow_handler.delete_workflow,
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/draft-graph",
            methods=["POST"],
            view_func=self.workflow_handler.update_draft_graph,
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/draft-graph",
            view_func=self.workflow_handler.get_draft_graph,
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/debug",
            methods=["POST"],
            view_func=self.workflow_handler.debug_workflow,
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/publish",
            methods=["POST"],
            view_func=self.workflow_handler.publish_workflow,
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/cancel-publish",
            methods=["POST"],
            view_func=self.workflow_handler.cancel_publish_workflow,
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/regenerate-icon",
            methods=["POST"],
            view_func=self.workflow_handler.regenerate_icon,
            endpoint="workflow_regenerate_icon",
        )
        bp.add_url_rule(
            "/workflows/generate-icon-preview",
            methods=["POST"],
            view_func=self.workflow_handler.generate_icon_preview,
            endpoint="workflow_generate_icon_preview",
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/share",
            methods=["POST"],
            view_func=self.workflow_handler.share_workflow_to_public,
        )

        # 12.语言模型模块
        bp.add_url_rule("/language-models", view_func=self.language_model_handler.get_language_models)
        bp.add_url_rule(
            "/language-models/<string:provider_name>/icon",
            view_func=self.language_model_handler.get_language_model_icon,
        )
        bp.add_url_rule(
            "/language-models/<string:provider_name>/<string:model_name>",
            view_func=self.language_model_handler.get_language_model,
        )

        # 13.辅助Agent模块
        bp.add_url_rule(
            "/assistant-agent/chat",
            methods=["POST"],
            view_func=self.assistant_agent_handler.assistant_agent_chat,
        )
        bp.add_url_rule(
            "/assistant-agent/introduction",
            methods=["POST"],
            view_func=self.assistant_agent_handler.generate_assistant_agent_introduction,
        )
        bp.add_url_rule(
            "/assistant-agent/chat/<uuid:task_id>/stop",
            methods=["POST"],
            view_func=self.assistant_agent_handler.stop_assistant_agent_chat,
        )
        bp.add_url_rule(
            "/assistant-agent/messages",
            view_func=self.assistant_agent_handler.get_assistant_agent_messages_with_page,
        )
        bp.add_url_rule(
            "/assistant-agent/conversations",
            view_func=self.assistant_agent_handler.get_assistant_agent_conversations,
        )
        bp.add_url_rule(
            "/assistant-agent/delete-conversation",
            methods=["POST"],
            view_func=self.assistant_agent_handler.delete_assistant_agent_conversation,
        )

        # 14.应用统计模块
        bp.add_url_rule(
            "/analysis/<uuid:app_id>",
            view_func=self.analysis_handler.get_app_analysis,
        )

        # 15.WebApp模块
        bp.add_url_rule("/web-apps/<string:token>", view_func=self.web_app_handler.get_web_app)
        bp.add_url_rule(
            "/web-apps/<string:token>/chat",
            methods=["POST"],
            view_func=self.web_app_handler.web_app_chat,
        )
        bp.add_url_rule(
            "/web-apps/<string:token>/chat/<uuid:task_id>/stop",
            methods=["POST"],
            view_func=self.web_app_handler.stop_web_app_chat,
        )
        bp.add_url_rule("/web-apps/<string:token>/conversations", view_func=self.web_app_handler.get_conversations)

        # 16.会话模块
        bp.add_url_rule(
            "/conversations/recent",
            view_func=self.conversation_handler.get_recent_conversations,
        )
        bp.add_url_rule(
            "/conversations/<uuid:conversation_id>/messages",
            view_func=self.conversation_handler.get_conversation_messages_with_page,
        )
        bp.add_url_rule(
            "/conversations/<uuid:conversation_id>/delete",
            methods=["POST"],
            view_func=self.conversation_handler.delete_conversation,
        )
        bp.add_url_rule(
            "/conversations/<uuid:conversation_id>/messages/<uuid:message_id>/delete",
            methods=["POST"],
            view_func=self.conversation_handler.delete_message,
        )
        # 兼容历史客户端：保留无 /delete 后缀的删除消息路由。
        bp.add_url_rule(
            "/conversations/<uuid:conversation_id>/messages/<uuid:message_id>",
            methods=["POST"],
            view_func=self.conversation_handler.delete_message,
        )
        bp.add_url_rule(
            "/conversations/<uuid:conversation_id>/name",
            view_func=self.conversation_handler.get_conversation_name,
        )
        bp.add_url_rule(
            "/conversations/<uuid:conversation_id>/name",
            methods=["POST"],
            view_func=self.conversation_handler.update_conversation_name,
        )
        bp.add_url_rule(
            "/conversations/<uuid:conversation_id>/is-pinned",
            methods=["POST"],
            view_func=self.conversation_handler.update_conversation_is_pinned,
        )
        bp.add_url_rule(
            "/conversations/search",
            view_func=self.conversation_handler.search_conversations,
        )

        # 17.语音转换模块
        bp.add_url_rule(
            "/audio/audio-to-text",
            methods=["POST"],
            view_func=self.audio_handler.audio_to_text,
        )
        bp.add_url_rule(
            "/audio/message-to-audio",
            methods=["POST"],
            view_func=self.audio_handler.message_to_audio,
        )
        bp.add_url_rule(
            "/audio/text-to-audio",
            methods=["POST"],
            view_func=self.audio_handler.text_to_audio,
        )
        # 18.第三方平台配置模块
        bp.add_url_rule(
            "/platform/<uuid:app_id>/wechat-config",
            view_func=self.platform_handler.get_wechat_config,
        )
        bp.add_url_rule(
            "/platform/<uuid:app_id>/wechat-config",
            methods=["POST"],
            view_func=self.platform_handler.update_wechat_config,
        )
        bp.add_url_rule(
            "/wechat/<uuid:app_id>",
            methods=["GET", "POST"],
            view_func=self.wechat_handler.wechat,
        )

        # 19.公共应用广场模块
        bp.add_url_rule(
            "/public/apps",
            view_func=self.public_app_handler.get_public_apps_with_page,
        )
        bp.add_url_rule(
            "/public/apps/<string:app_id>",
            view_func=self.public_app_handler.get_public_app_detail,
        )
        bp.add_url_rule(
            "/public/apps/<string:app_id>/analysis",
            view_func=self.public_app_handler.get_public_app_analysis,
        )
        bp.add_url_rule(
            "/public/apps/tags",
            view_func=self.public_app_handler.get_app_tags,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/share-to-square",
            methods=["POST"],
            view_func=self.public_app_handler.share_app_to_square,
        )
        bp.add_url_rule(
            "/apps/<uuid:app_id>/unshare-from-square",
            methods=["POST"],
            view_func=self.public_app_handler.unshare_app_from_square,
        )
        bp.add_url_rule(
            "/public/apps/<string:app_id>/fork",
            methods=["POST"],
            view_func=self.public_app_handler.fork_public_app,
        )
        bp.add_url_rule(
            "/public/apps/<uuid:app_id>/like",
            methods=["POST"],
            view_func=self.public_app_handler.like_app,
        )
        bp.add_url_rule(
            "/public/apps/<uuid:app_id>/favorite",
            methods=["POST"],
            view_func=self.public_app_handler.favorite_app,
        )
        bp.add_url_rule(
            "/public/apps/my-favorites",
            view_func=self.public_app_handler.get_my_favorites,
        )

        # 20.公共工作流广场模块
        bp.add_url_rule(
            "/public/workflows",
            view_func=self.public_workflow_handler.get_public_workflows_with_page,
        )
        bp.add_url_rule(
            "/public/workflows/<uuid:workflow_id>",
            view_func=self.public_workflow_handler.get_public_workflow_detail,
        )
        bp.add_url_rule(
            "/public/workflows/<uuid:workflow_id>/draft-graph",
            view_func=self.public_workflow_handler.get_public_workflow_draft_graph,
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/share-to-square",
            methods=["POST"],
            view_func=self.public_workflow_handler.share_workflow_to_square,
        )
        bp.add_url_rule(
            "/workflows/<uuid:workflow_id>/unshare-from-square",
            methods=["POST"],
            view_func=self.public_workflow_handler.unshare_workflow_from_square,
        )
        bp.add_url_rule(
            "/public/workflows/<uuid:workflow_id>/fork",
            methods=["POST"],
            view_func=self.public_workflow_handler.fork_public_workflow,
        )
        bp.add_url_rule(
            "/public/workflows/<uuid:workflow_id>/like",
            methods=["POST"],
            view_func=self.public_workflow_handler.like_workflow,
        )
        bp.add_url_rule(
            "/public/workflows/<uuid:workflow_id>/favorite",
            methods=["POST"],
            view_func=self.public_workflow_handler.favorite_workflow,
        )

        # 21.通知模块
        bp.add_url_rule("/notifications", view_func=self.notification_handler.get_notifications)
        bp.add_url_rule(
            "/notifications/<string:notification_id>/read",
            methods=["POST"],
            view_func=self.notification_handler.mark_notification_as_read,
        )
        bp.add_url_rule(
            "/notifications/<string:notification_id>",
            methods=["DELETE"],
            view_func=self.notification_handler.delete_notification,
        )

        # 22.在应用上注册蓝图
        app.register_blueprint(bp)
        app.register_blueprint(openapi_bp)

