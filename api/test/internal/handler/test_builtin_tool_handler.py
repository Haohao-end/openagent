from pkg.response import HttpCode
import pytest

class TestBuiltinToolHandler:
    """内置工具处理器测试类"""

    @pytest.fixture
    def http_client(self, app):
        """使用独立客户端，避免触发全局 client->db 自动事务夹具。"""
        with app.test_client() as client:
            yield client

    def test_get_categories(self, http_client):
        """测试所有分类信息"""
        resp = http_client.get("/builtin-tools/categories")
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        assert len(resp.json.get("data")) > 0

    def test_get_builtin_tools(self, http_client):
        """测试获取所有内置工具"""
        resp = http_client.get("/builtin-tools")
        assert resp.status_code == 200
        assert resp.json.get("code") == HttpCode.SUCCESS
        assert len(resp.json.get("data")) > 0

    @pytest.mark.parametrize(
        "provider_name,tool_name",
        [
            ("google","google_serper")
        ]
    )
    def test_get_provider_tool(self, provider_name, tool_name, http_client):
        """测试获取指定工具信息接口"""
        resp = http_client.get(f"/builtin-tools/{provider_name}/tools/{tool_name}")
        assert resp.status_code == 200
        if provider_name == resp.json.get("data").get("name"):
            assert resp.json.get("code") == HttpCode.SUCCESS
            assert resp.json.get("data").get("name") == tool_name


    @pytest.mark.parametrize(
        "provider_name",
        ["google","haohao"]
    )
    def test_get_provider_icon(self, provider_name, http_client):
        """测试根据提供商名字获取icon接口"""
        resp = http_client.get(f"/builtin-tools/{provider_name}/icon")
        if provider_name == "haohao":
            assert resp.status_code == 200
            assert resp.json.get("code") == HttpCode.NOT_FOUND
            return

        assert resp.status_code in (200, 302)

    def test_get_provider_icon_should_redirect_when_provider_icon_is_remote_url(self, http_client):
        """测试当 provider icon 为远程地址时应返回重定向"""
        resp = http_client.get("/builtin-tools/tavily/icon")

        assert resp.status_code == 302
        assert resp.headers["Location"].startswith("https://")

    def test_get_provider_icon_should_return_empty_bytes_when_icon_is_none(self, http_client, monkeypatch):
        monkeypatch.setattr(
            "internal.service.builtin_tool_service.BuiltinToolService.get_provider_icon",
            lambda *_args, **_kwargs: (None, "image/png", ""),
        )

        resp = http_client.get("/builtin-tools/google/icon")

        assert resp.status_code == 200
        assert resp.mimetype == "image/png"
        assert resp.data == b""

    def test_get_provider_icon_should_return_raw_icon_bytes_when_icon_exists(self, http_client, monkeypatch):
        monkeypatch.setattr(
            "internal.service.builtin_tool_service.BuiltinToolService.get_provider_icon",
            lambda *_args, **_kwargs: (b"\x89PNG", "image/png", ""),
        )

        resp = http_client.get("/builtin-tools/google/icon")

        assert resp.status_code == 200
        assert resp.mimetype == "image/png"
        assert resp.data == b"\x89PNG"
