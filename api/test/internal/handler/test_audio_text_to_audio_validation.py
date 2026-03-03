import pytest

from pkg.response import HttpCode


class TestAudioTextToAudioValidation:
    @pytest.fixture
    def http_client(self, app):
        with app.test_client() as client:
            yield client

    def test_should_return_validate_error_when_text_missing(self, http_client, monkeypatch):
        monkeypatch.setattr(
            "internal.service.audio_service.AudioService.text_to_audio",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("参数校验失败时不应调用service")),
        )

        resp = http_client.post("/audio/text-to-audio", json={})

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.VALIDATE_ERROR

    def test_should_return_validate_error_when_text_too_long(self, http_client, monkeypatch):
        monkeypatch.setattr(
            "internal.service.audio_service.AudioService.text_to_audio",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("参数校验失败时不应调用service")),
        )

        resp = http_client.post("/audio/text-to-audio", json={"text": "x" * 5001})

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.VALIDATE_ERROR
