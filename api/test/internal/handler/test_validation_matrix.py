import pytest

from pkg.response import HttpCode


APP_ID = "00000000-0000-0000-0000-000000000001"
PROVIDER_ID = "00000000-0000-0000-0000-000000000002"
DATASET_ID = "00000000-0000-0000-0000-000000000003"
DOCUMENT_ID = "00000000-0000-0000-0000-000000000004"
SEGMENT_ID = "00000000-0000-0000-0000-000000000005"
WORKFLOW_ID = "00000000-0000-0000-0000-000000000006"
CONVERSATION_ID = "00000000-0000-0000-0000-000000000007"


CASES = [
    # app
    {"name": "create_app_missing_required", "method": "post", "url": "/apps", "kwargs": {"json": {}}},
    {
        "name": "create_app_invalid_icon",
        "method": "post",
        "url": "/apps",
        "kwargs": {"json": {"name": "demo", "icon": "not-url"}},
    },
    {"name": "update_app_missing_required", "method": "post", "url": f"/apps/{APP_ID}", "kwargs": {"json": {}}},
    {
        "name": "fallback_history_missing_required",
        "method": "post",
        "url": f"/apps/{APP_ID}/fallback-history",
        "kwargs": {"json": {}},
    },
    {
        "name": "fallback_history_invalid_uuid",
        "method": "post",
        "url": f"/apps/{APP_ID}/fallback-history",
        "kwargs": {"json": {"app_config_version_id": "not-uuid"}},
    },
    {"name": "debug_chat_missing_query", "method": "post", "url": f"/apps/{APP_ID}/conversations", "kwargs": {"json": {}}},
    {
        "name": "debug_chat_image_over_limit",
        "method": "post",
        "url": f"/apps/{APP_ID}/conversations",
        "kwargs": {"json": {"query": "hello", "image_urls": ["a", "b", "c", "d", "e", "f"]}},
    },
    {
        "name": "prompt_compare_missing_required",
        "method": "post",
        "url": f"/apps/{APP_ID}/prompt-compare/chat",
        "kwargs": {"json": {}},
    },
    # api tool
    {
        "name": "validate_openapi_schema_missing",
        "method": "post",
        "url": "/api-tools/validate-openapi-schema",
        "kwargs": {"json": {}},
    },
    {"name": "create_api_tool_missing_required", "method": "post", "url": "/api-tools", "kwargs": {"json": {}}},
    {
        "name": "create_api_tool_invalid_icon",
        "method": "post",
        "url": "/api-tools",
        "kwargs": {"json": {"name": "tool", "icon": "not-url", "openapi_schema": "{}"}},
    },
    {
        "name": "update_api_tool_missing_required",
        "method": "post",
        "url": f"/api-tools/{PROVIDER_ID}",
        "kwargs": {"json": {}},
    },
    # account
    {"name": "send_change_email_code_missing", "method": "post", "url": "/account/email/send-code", "kwargs": {"json": {}}},
    {"name": "send_change_email_code_invalid", "method": "post", "url": "/account/email/send-code", "kwargs": {"json": {"email": "bad-email"}}},
    {"name": "get_account_login_history_invalid_page", "method": "get", "url": "/account/login-history", "kwargs": {"query_string": {"current_page": 0}}},
    {"name": "get_account_login_history_invalid_status", "method": "get", "url": "/account/login-history", "kwargs": {"query_string": {"status": "weird"}}},
    {"name": "update_email_missing", "method": "post", "url": "/account/email", "kwargs": {"json": {}}},
    {"name": "update_email_invalid_code", "method": "post", "url": "/account/email", "kwargs": {"json": {"email": "next@example.com", "code": "12"}}},
    {"name": "update_email_password_too_long", "method": "post", "url": "/account/email", "kwargs": {"json": {"email": "next@example.com", "code": "123456", "current_password": "x" * 129}}},
    {"name": "update_password_missing", "method": "post", "url": "/account/password", "kwargs": {"json": {}}},
    {"name": "update_password_weak", "method": "post", "url": "/account/password", "kwargs": {"json": {"new_password": "123"}}},
    {"name": "update_name_missing", "method": "post", "url": "/account/name", "kwargs": {"json": {}}},
    {"name": "update_avatar_missing", "method": "post", "url": "/account/avatar", "kwargs": {"json": {}}},
    {"name": "update_avatar_invalid_url", "method": "post", "url": "/account/avatar", "kwargs": {"json": {"avatar": "bad"}}},
    # dataset/document/segment
    {"name": "create_dataset_missing_required", "method": "post", "url": "/datasets", "kwargs": {"json": {}}},
    {
        "name": "create_dataset_invalid_icon",
        "method": "post",
        "url": "/datasets",
        "kwargs": {"json": {"name": "ds", "icon": "bad"}},
    },
    {"name": "update_dataset_missing_required", "method": "post", "url": f"/datasets/{DATASET_ID}", "kwargs": {"json": {}}},
    {"name": "dataset_hit_missing_required", "method": "post", "url": f"/datasets/{DATASET_ID}/hit", "kwargs": {"json": {}}},
    {
        "name": "dataset_hit_invalid_strategy",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/hit",
        "kwargs": {"json": {"query": "hello", "retrieval_strategy": "bad", "k": 2}},
    },
    {"name": "create_documents_missing_required", "method": "post", "url": f"/datasets/{DATASET_ID}/documents", "kwargs": {"json": {}}},
    {
        "name": "update_document_name_missing_required",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/name",
        "kwargs": {"json": {}},
    },
    {
        "name": "create_segment_missing_required",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments",
        "kwargs": {"json": {}},
    },
    {
        "name": "update_segment_missing_required",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments/{SEGMENT_ID}",
        "kwargs": {"json": {}},
    },
    # ai
    {"name": "optimize_prompt_missing_required", "method": "post", "url": "/ai/optimize-prompt", "kwargs": {"json": {}}},
    {"name": "suggested_questions_missing_required", "method": "post", "url": "/ai/suggested-questions", "kwargs": {"json": {}}},
    {"name": "openapi_schema_chat_missing_required", "method": "post", "url": "/ai/openapi-schema-chat", "kwargs": {"json": {}}},
    # assistant agent
    {"name": "assistant_chat_missing_query", "method": "post", "url": "/assistant-agent/chat", "kwargs": {"json": {}}},
    # audio
    {"name": "message_to_audio_missing_required", "method": "post", "url": "/audio/message-to-audio", "kwargs": {"json": {}}},
    {"name": "audio_to_text_missing_file", "method": "post", "url": "/audio/audio-to-text", "kwargs": {"data": {}}},
    {"name": "text_to_audio_missing_required", "method": "post", "url": "/audio/text-to-audio", "kwargs": {"json": {}}},
    # auth/oauth/openapi/web app
    {"name": "password_login_missing_required", "method": "post", "url": "/auth/password-login", "kwargs": {"json": {}}},
    {"name": "verify_login_challenge_missing_required", "method": "post", "url": "/auth/login-challenge/verify", "kwargs": {"json": {}}},
    {"name": "resend_login_challenge_missing_required", "method": "post", "url": "/auth/login-challenge/resend", "kwargs": {"json": {}}},
    {"name": "oauth_authorize_missing_required", "method": "post", "url": "/oauth/authorize/github", "kwargs": {"json": {}}},
    {"name": "openapi_chat_missing_required", "method": "post", "url": "/openapi/chat", "kwargs": {"json": {}}},
    {
        "name": "openapi_chat_invalid_app_id",
        "method": "post",
        "url": "/openapi/chat",
        "kwargs": {"json": {"app_id": "bad", "query": "hi"}},
    },
    {"name": "web_app_chat_missing_required", "method": "post", "url": "/web-apps/test-token/chat", "kwargs": {"json": {}}},
    # workflow/conversation
    {"name": "create_workflow_missing_required", "method": "post", "url": "/workflows", "kwargs": {"json": {}}},
    {"name": "update_workflow_missing_required", "method": "post", "url": f"/workflows/{WORKFLOW_ID}", "kwargs": {"json": {}}},
    {
        "name": "update_conversation_name_missing_required",
        "method": "post",
        "url": f"/conversations/{CONVERSATION_ID}/name",
        "kwargs": {"json": {}},
    },
]

CASES += [
    # app extra
    {
        "name": "create_app_name_too_long",
        "method": "post",
        "url": "/apps",
        "kwargs": {"json": {"name": "x" * 41, "icon": "https://a.com/a.png"}},
    },
    {
        "name": "update_app_name_too_long",
        "method": "post",
        "url": f"/apps/{APP_ID}",
        "kwargs": {"json": {"name": "x" * 41, "icon": "https://a.com/a.png"}},
    },
    {
        "name": "update_app_invalid_icon",
        "method": "post",
        "url": f"/apps/{APP_ID}",
        "kwargs": {"json": {"name": "demo", "icon": "bad"}},
    },
    {
        "name": "get_apps_with_page_invalid_current_page",
        "method": "get",
        "url": "/apps",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "get_apps_with_page_invalid_page_size",
        "method": "get",
        "url": "/apps",
        "kwargs": {"query_string": {"page_size": 51}},
    },
    {
        "name": "get_publish_histories_invalid_current_page",
        "method": "get",
        "url": f"/apps/{APP_ID}/publish-histories",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "debug_chat_invalid_image_url",
        "method": "post",
        "url": f"/apps/{APP_ID}/conversations",
        "kwargs": {"json": {"query": "hello", "image_urls": ["not-url"]}},
    },
    {
        "name": "get_debug_messages_invalid_created_at",
        "method": "get",
        "url": f"/apps/{APP_ID}/conversations/messages",
        "kwargs": {"query_string": {"created_at": -1}},
    },
    {
        "name": "get_debug_messages_invalid_current_page",
        "method": "get",
        "url": f"/apps/{APP_ID}/conversations/messages",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    # api tools extra
    {
        "name": "validate_openapi_schema_empty",
        "method": "post",
        "url": "/api-tools/validate-openapi-schema",
        "kwargs": {"json": {"openapi_schema": ""}},
    },
    {
        "name": "create_api_tool_headers_not_list",
        "method": "post",
        "url": "/api-tools",
        "kwargs": {
            "json": {
                "name": "tool",
                "icon": "https://a.com/a.png",
                "openapi_schema": "{}",
                "headers": "x",
            }
        },
    },
    {
        "name": "create_api_tool_header_not_dict",
        "method": "post",
        "url": "/api-tools",
        "kwargs": {
            "json": {
                "name": "tool",
                "icon": "https://a.com/a.png",
                "openapi_schema": "{}",
                "headers": ["x"],
            }
        },
    },
    {
        "name": "create_api_tool_header_missing_key_value",
        "method": "post",
        "url": "/api-tools",
        "kwargs": {
            "json": {
                "name": "tool",
                "icon": "https://a.com/a.png",
                "openapi_schema": "{}",
                "headers": [{"key": "A"}],
            }
        },
    },
    {
        "name": "create_api_tool_name_too_long",
        "method": "post",
        "url": "/api-tools",
        "kwargs": {
            "json": {
                "name": "x" * 31,
                "icon": "https://a.com/a.png",
                "openapi_schema": "{}",
            }
        },
    },
    {
        "name": "update_api_tool_header_not_dict",
        "method": "post",
        "url": f"/api-tools/{PROVIDER_ID}",
        "kwargs": {
            "json": {
                "name": "tool",
                "icon": "https://a.com/a.png",
                "openapi_schema": "{}",
                "headers": ["x"],
            }
        },
    },
    {
        "name": "update_api_tool_header_missing_key_value",
        "method": "post",
        "url": f"/api-tools/{PROVIDER_ID}",
        "kwargs": {
            "json": {
                "name": "tool",
                "icon": "https://a.com/a.png",
                "openapi_schema": "{}",
                "headers": [{"value": "x"}],
            }
        },
    },
    {
        "name": "get_api_tools_with_page_invalid_current_page",
        "method": "get",
        "url": "/api-tools",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "get_api_tools_with_page_invalid_page_size",
        "method": "get",
        "url": "/api-tools",
        "kwargs": {"query_string": {"page_size": 999}},
    },
    # account extra
    {
        "name": "update_name_too_long",
        "method": "post",
        "url": "/account/name",
        "kwargs": {"json": {"name": "x" * 31}},
    },
    # datasets extra
    {
        "name": "create_dataset_name_too_long",
        "method": "post",
        "url": "/datasets",
        "kwargs": {"json": {"name": "x" * 101, "icon": "https://a.com/a.png"}},
    },
    {
        "name": "update_dataset_name_too_long",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}",
        "kwargs": {"json": {"name": "x" * 101, "icon": "https://a.com/a.png"}},
    },
    {
        "name": "dataset_hit_k_too_small",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/hit",
        "kwargs": {"json": {"query": "hello", "retrieval_strategy": "semantic_search", "k": 0}},
    },
    {
        "name": "dataset_hit_k_too_large",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/hit",
        "kwargs": {"json": {"query": "hello", "retrieval_strategy": "semantic_search", "k": 11}},
    },
    {
        "name": "dataset_hit_score_too_large",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/hit",
        "kwargs": {"json": {"query": "hello", "retrieval_strategy": "semantic_search", "k": 2, "score": 1.1}},
    },
    {
        "name": "get_datasets_with_page_invalid_current_page",
        "method": "get",
        "url": "/datasets",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "get_datasets_with_page_invalid_page_size",
        "method": "get",
        "url": "/datasets",
        "kwargs": {"query_string": {"page_size": 999}},
    },
    # documents extra
    {
        "name": "create_documents_invalid_process_type",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents",
        "kwargs": {"json": {"upload_file_ids": [APP_ID], "process_type": "bad", "rule": {}}},
    },
    {
        "name": "create_documents_upload_file_ids_not_list",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents",
        "kwargs": {"json": {"upload_file_ids": "x", "process_type": "automatic", "rule": {}}},
    },
    {
        "name": "create_documents_upload_file_ids_too_many",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents",
        "kwargs": {
            "json": {
                "upload_file_ids": [APP_ID] * 11,
                "process_type": "automatic",
                "rule": {},
            }
        },
    },
    {
        "name": "create_documents_upload_file_ids_invalid_uuid",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents",
        "kwargs": {
            "json": {
                "upload_file_ids": ["bad-uuid"],
                "process_type": "automatic",
                "rule": {},
            }
        },
    },
    {
        "name": "create_documents_custom_rule_missing",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents",
        "kwargs": {"json": {"upload_file_ids": [APP_ID], "process_type": "custom"}},
    },
    {
        "name": "create_documents_custom_rule_bad_pre_process",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents",
        "kwargs": {
            "json": {
                "upload_file_ids": [APP_ID],
                "process_type": "custom",
                "rule": {
                    "pre_process_rules": [{"id": "remove_extra_space", "enabled": True}],
                    "segment": {"separators": ["\n"], "chunk_size": 300, "chunk_overlap": 50},
                },
            }
        },
    },
    {
        "name": "update_document_name_too_long",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/name",
        "kwargs": {"json": {"name": "x" * 101}},
    },
    {
        "name": "get_documents_with_page_invalid_current_page",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/documents",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "get_documents_with_page_invalid_page_size",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/documents",
        "kwargs": {"query_string": {"page_size": 999}},
    },
    # segments extra
    {
        "name": "create_segment_keywords_not_list",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments",
        "kwargs": {"json": {"content": "hello", "keywords": "x"}},
    },
    {
        "name": "create_segment_keywords_too_many",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments",
        "kwargs": {"json": {"content": "hello", "keywords": list("abcdefghijk")}},
    },
    {
        "name": "get_segments_with_page_invalid_current_page",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "get_segments_with_page_invalid_page_size",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments",
        "kwargs": {"query_string": {"page_size": 999}},
    },
    {
        "name": "update_segment_keywords_not_list",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments/{SEGMENT_ID}",
        "kwargs": {"json": {"content": "hello", "keywords": "x"}},
    },
    {
        "name": "update_segment_keywords_too_many",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments/{SEGMENT_ID}",
        "kwargs": {"json": {"content": "hello", "keywords": list("abcdefghijk")}},
    },
    # ai extra
    {
        "name": "optimize_prompt_too_long",
        "method": "post",
        "url": "/ai/optimize-prompt",
        "kwargs": {"json": {"prompt": "x" * 2001}},
    },
    {
        "name": "suggested_questions_invalid_uuid",
        "method": "post",
        "url": "/ai/suggested-questions",
        "kwargs": {"json": {"message_id": "bad"}},
    },
    # assistant extra
    {
        "name": "assistant_chat_image_over_limit",
        "method": "post",
        "url": "/assistant-agent/chat",
        "kwargs": {"json": {"query": "hi", "image_urls": ["a", "b", "c", "d", "e", "f"]}},
    },
    {
        "name": "assistant_chat_invalid_image_url",
        "method": "post",
        "url": "/assistant-agent/chat",
        "kwargs": {"json": {"query": "hi", "image_urls": ["bad"]}},
    },
    {
        "name": "assistant_messages_invalid_created_at",
        "method": "get",
        "url": "/assistant-agent/messages",
        "kwargs": {"query_string": {"created_at": -1}},
    },
    {
        "name": "assistant_messages_invalid_current_page",
        "method": "get",
        "url": "/assistant-agent/messages",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    # audio extra
    {
        "name": "message_to_audio_empty_message_id",
        "method": "post",
        "url": "/audio/message-to-audio",
        "kwargs": {"json": {"message_id": ""}},
    },
    {
        "name": "text_to_audio_text_too_long",
        "method": "post",
        "url": "/audio/text-to-audio",
        "kwargs": {"json": {"text": "x" * 5001}},
    },
    # auth/oauth/openapi extra
    {
        "name": "password_login_invalid_email",
        "method": "post",
        "url": "/auth/password-login",
        "kwargs": {"json": {"email": "bad", "password": "Abcd1234"}},
    },
    {
        "name": "password_login_empty_password",
        "method": "post",
        "url": "/auth/password-login",
        "kwargs": {"json": {"email": "a@b.com", "password": ""}},
    },
    {
        "name": "openapi_chat_invalid_end_user_id",
        "method": "post",
        "url": "/openapi/chat",
        "kwargs": {"json": {"app_id": APP_ID, "end_user_id": "bad", "query": "hi"}},
    },
    {
        "name": "openapi_chat_invalid_conversation_id",
        "method": "post",
        "url": "/openapi/chat",
        "kwargs": {"json": {"app_id": APP_ID, "end_user_id": APP_ID, "conversation_id": "bad", "query": "hi"}},
    },
    {
        "name": "openapi_chat_conversation_without_end_user",
        "method": "post",
        "url": "/openapi/chat",
        "kwargs": {"json": {"app_id": APP_ID, "conversation_id": APP_ID, "query": "hi"}},
    },
    {
        "name": "openapi_chat_image_over_limit",
        "method": "post",
        "url": "/openapi/chat",
        "kwargs": {"json": {"app_id": APP_ID, "query": "hi", "image_urls": ["a", "b", "c", "d", "e", "f"]}},
    },
    {
        "name": "openapi_chat_invalid_image_url",
        "method": "post",
        "url": "/openapi/chat",
        "kwargs": {"json": {"app_id": APP_ID, "query": "hi", "image_urls": ["bad"]}},
    },
    # workflow extra
    {
        "name": "create_workflow_invalid_tool_call_name",
        "method": "post",
        "url": "/workflows",
        "kwargs": {
            "json": {
                "name": "wf",
                "tool_call_name": "bad-name",
                "icon": "https://a.com/a.png",
                "description": "desc",
            }
        },
    },
    {
        "name": "create_workflow_invalid_icon",
        "method": "post",
        "url": "/workflows",
        "kwargs": {
            "json": {
                "name": "wf",
                "tool_call_name": "ok_name",
                "icon": "bad",
                "description": "desc",
            }
        },
    },
    {
        "name": "create_workflow_description_too_long",
        "method": "post",
        "url": "/workflows",
        "kwargs": {
            "json": {
                "name": "wf",
                "tool_call_name": "ok_name",
                "icon": "https://a.com/a.png",
                "description": "x" * 1025,
            }
        },
    },
    {
        "name": "update_workflow_invalid_tool_call_name",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}",
        "kwargs": {
            "json": {
                "name": "wf",
                "tool_call_name": "bad-name",
                "icon": "https://a.com/a.png",
                "description": "desc",
            }
        },
    },
    {
        "name": "get_workflows_invalid_status",
        "method": "get",
        "url": "/workflows",
        "kwargs": {"query_string": {"status": "bad"}},
    },
    {
        "name": "get_workflows_invalid_current_page",
        "method": "get",
        "url": "/workflows",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "get_workflows_invalid_page_size",
        "method": "get",
        "url": "/workflows",
        "kwargs": {"query_string": {"page_size": 999}},
    },
    # web app extra
    {
        "name": "web_app_chat_invalid_conversation_id",
        "method": "post",
        "url": "/web-apps/test-token/chat",
        "kwargs": {"json": {"conversation_id": "bad", "query": "hi"}},
    },
    {
        "name": "web_app_chat_invalid_image_url",
        "method": "post",
        "url": "/web-apps/test-token/chat",
        "kwargs": {"json": {"query": "hi", "image_urls": ["bad"]}},
    },
    {
        "name": "web_app_chat_image_over_limit",
        "method": "post",
        "url": "/web-apps/test-token/chat",
        "kwargs": {"json": {"query": "hi", "image_urls": ["a", "b", "c", "d", "e", "f"]}},
    },
    # conversation extra
    {
        "name": "get_conversation_messages_invalid_created_at",
        "method": "get",
        "url": f"/conversations/{CONVERSATION_ID}/messages",
        "kwargs": {"query_string": {"created_at": -1}},
    },
    {
        "name": "get_conversation_messages_invalid_current_page",
        "method": "get",
        "url": f"/conversations/{CONVERSATION_ID}/messages",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "update_conversation_name_too_long",
        "method": "post",
        "url": f"/conversations/{CONVERSATION_ID}/name",
        "kwargs": {"json": {"name": "x" * 101}},
    },
    # upload file/api key extra
    {"name": "upload_file_missing", "method": "post", "url": "/upload-files/file", "kwargs": {"data": {}}},
    {"name": "upload_image_missing", "method": "post", "url": "/upload-files/image", "kwargs": {"data": {}}},
    {
        "name": "create_api_key_remark_too_long",
        "method": "post",
        "url": "/openapi/api-keys",
        "kwargs": {"json": {"remark": "x" * 101}},
    },
    {
        "name": "update_api_key_remark_too_long",
        "method": "post",
        "url": f"/openapi/api-keys/{PROVIDER_ID}",
        "kwargs": {"json": {"remark": "x" * 101}},
    },
    {
        "name": "get_api_keys_invalid_current_page",
        "method": "get",
        "url": "/openapi/api-keys",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "get_api_keys_invalid_page_size",
        "method": "get",
        "url": "/openapi/api-keys",
        "kwargs": {"query_string": {"page_size": 999}},
    },
]


class TestValidationMatrix:
    """高频接口参数校验矩阵测试。"""

    @pytest.fixture
    def http_client(self, app):
        """
        校验矩阵只验证 request schema，不需要访问数据库。
        这里使用独立客户端名称，避免触发全局 `client -> db` 自动事务夹具。
        """
        with app.test_client() as client:
            yield client

    @pytest.mark.parametrize("case", CASES, ids=[item["name"] for item in CASES])
    def test_required_fields_and_format_validation(self, case, http_client):
        method = getattr(http_client, case["method"])
        resp = method(case["url"], **case["kwargs"])

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.VALIDATE_ERROR
