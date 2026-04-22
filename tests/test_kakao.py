from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from news_briefing.delivery.kakao import (
    KakaoTokens,
    compose_text_template,
    load_tokens,
    save_tokens,
    send_text,
)


def test_tokens_roundtrip(tmp_path: Path) -> None:
    t = KakaoTokens(access_token="a", refresh_token="r", expires_at="2026-04-22T06:00:00Z")
    path = tmp_path / ".kakao_tokens.json"
    save_tokens(path, t)
    loaded = load_tokens(path)
    assert loaded == t


def test_load_tokens_missing_returns_none(tmp_path: Path) -> None:
    assert load_tokens(tmp_path / "absent.json") is None


def test_compose_text_template_structure() -> None:
    payload = compose_text_template(
        title="데일리 브리핑 · 4월 22일\n공시 3건",
        url="https://news-briefing.vercel.app/?tab=economy",
        button_title="열기",
    )
    assert payload["object_type"] == "text"
    assert payload["text"].startswith("데일리 브리핑")
    assert payload["link"]["web_url"].startswith("https://")
    assert payload["button_title"] == "열기"


def test_send_text_posts_to_kakao_api(mocker) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result_code": 0}
    mock_post = mocker.patch(
        "news_briefing.delivery.kakao.requests.post", return_value=mock_resp
    )
    tokens = KakaoTokens(access_token="abc", refresh_token="r", expires_at=None)
    payload = compose_text_template("hi", "https://x.com", "열기")
    ok = send_text(tokens=tokens, rest_api_key="", payload=payload)
    assert ok is True
    args, kwargs = mock_post.call_args
    assert "kapi.kakao.com" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer abc"
    # template_object 는 form-encoded JSON string
    assert "template_object" in kwargs["data"]
    assert json.loads(kwargs["data"]["template_object"])["object_type"] == "text"


def test_send_text_returns_false_on_non_200(mocker) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "unauthorized"
    mocker.patch("news_briefing.delivery.kakao.requests.post", return_value=mock_resp)
    tokens = KakaoTokens(access_token="abc", refresh_token="r", expires_at=None)
    ok = send_text(tokens=tokens, rest_api_key="", payload={"object_type": "text"})
    assert ok is False
