from types import SimpleNamespace

import pytest

from internal.exception import UnauthorizedException
from internal.middleware.middleware import Middleware


def test_validate_credential_should_raise_when_authorization_missing():
    request = SimpleNamespace(headers={})

    with pytest.raises(UnauthorizedException, match="需要授权"):
        Middleware._validate_credential(request)


def test_validate_credential_should_raise_when_format_has_no_space():
    request = SimpleNamespace(headers={"Authorization": "BearerOnlyToken"})

    with pytest.raises(UnauthorizedException, match="验证格式失败"):
        Middleware._validate_credential(request)


def test_validate_credential_should_raise_when_schema_not_bearer():
    request = SimpleNamespace(headers={"Authorization": "Basic token"})

    with pytest.raises(UnauthorizedException, match="验证格式失败"):
        Middleware._validate_credential(request)


def test_validate_credential_should_return_credential_when_valid():
    request = SimpleNamespace(headers={"Authorization": "Bearer token-123"})

    credential = Middleware._validate_credential(request)

    assert credential == "token-123"


def test_request_loader_should_load_account_for_llmops_blueprint():
    parse_calls = []
    account_calls = []
    middleware = Middleware(
        jwt_service=SimpleNamespace(
            parse_token=lambda token: parse_calls.append(token) or {"sub": "account-id-1"}
        ),
        api_key_service=SimpleNamespace(get_api_by_by_credential=lambda _k: None),
        account_service=SimpleNamespace(
            get_account=lambda account_id: account_calls.append(account_id) or {"id": account_id}
        ),
    )
    request = SimpleNamespace(
        blueprint="llmops",
        headers={"Authorization": "Bearer jwt-token"},
    )

    account = middleware.request_loader(request)

    assert parse_calls == ["jwt-token"]
    assert account_calls == ["account-id-1"]
    assert account == {"id": "account-id-1"}


def test_request_loader_should_raise_when_openapi_api_key_not_found():
    middleware = Middleware(
        jwt_service=SimpleNamespace(parse_token=lambda _token: {}),
        api_key_service=SimpleNamespace(get_api_by_by_credential=lambda _key: None),
        account_service=SimpleNamespace(get_account=lambda _id: None),
    )
    request = SimpleNamespace(
        blueprint="openapi",
        headers={"Authorization": "Bearer api-key"},
    )

    with pytest.raises(UnauthorizedException, match="不存在或未激活"):
        middleware.request_loader(request)


def test_request_loader_should_raise_when_openapi_api_key_inactive():
    middleware = Middleware(
        jwt_service=SimpleNamespace(parse_token=lambda _token: {}),
        api_key_service=SimpleNamespace(
            get_api_by_by_credential=lambda _key: SimpleNamespace(is_active=False, account=None)
        ),
        account_service=SimpleNamespace(get_account=lambda _id: None),
    )
    request = SimpleNamespace(
        blueprint="openapi",
        headers={"Authorization": "Bearer api-key"},
    )

    with pytest.raises(UnauthorizedException, match="不存在或未激活"):
        middleware.request_loader(request)


def test_request_loader_should_return_account_when_openapi_api_key_active():
    expected_account = {"id": "acc-1"}
    middleware = Middleware(
        jwt_service=SimpleNamespace(parse_token=lambda _token: {}),
        api_key_service=SimpleNamespace(
            get_api_by_by_credential=lambda _key: SimpleNamespace(is_active=True, account=expected_account)
        ),
        account_service=SimpleNamespace(get_account=lambda _id: None),
    )
    request = SimpleNamespace(
        blueprint="openapi",
        headers={"Authorization": "Bearer api-key"},
    )

    account = middleware.request_loader(request)

    assert account == expected_account


def test_request_loader_should_return_none_for_unmatched_blueprint():
    middleware = Middleware(
        jwt_service=SimpleNamespace(parse_token=lambda _token: {}),
        api_key_service=SimpleNamespace(get_api_by_by_credential=lambda _key: None),
        account_service=SimpleNamespace(get_account=lambda _id: None),
    )
    request = SimpleNamespace(blueprint="health-check", headers={})

    assert middleware.request_loader(request) is None
