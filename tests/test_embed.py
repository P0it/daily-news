from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from news_briefing.analysis.embed import embed, embed_hash, embed_ollama


def test_embed_ollama_success(mocker) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    mocker.patch(
        "news_briefing.analysis.embed.requests.post", return_value=mock_resp
    )
    v = embed_ollama("hello", model="nomic-embed-text")
    assert v is not None
    np.testing.assert_allclose(v, [0.1, 0.2, 0.3])


def test_embed_ollama_failure_returns_none(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.embed.requests.post",
        side_effect=Exception("conn refused"),
    )
    assert embed_ollama("x", model="any") is None


def test_embed_ollama_non_200_returns_none(mocker) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mocker.patch(
        "news_briefing.analysis.embed.requests.post", return_value=mock_resp
    )
    assert embed_ollama("x", model="any") is None


def test_embed_hash_is_deterministic() -> None:
    a = embed_hash("삼성전자 자사주 매수")
    b = embed_hash("삼성전자 자사주 매수")
    np.testing.assert_allclose(a, b)


def test_embed_hash_different_inputs_different_vectors() -> None:
    a = embed_hash("로봇")
    b = embed_hash("전혀 다른 이야기")
    cos = float(np.dot(a, b))
    assert cos < 0.95


def test_embed_falls_back_to_hash_when_ollama_fails(mocker) -> None:
    mocker.patch("news_briefing.analysis.embed.embed_ollama", return_value=None)
    v = embed("hello world", model="x")
    assert v.shape[0] == 256


def test_embed_empty_returns_zero_vector() -> None:
    v = embed("   ", model="x")
    assert float(np.linalg.norm(v)) == 0.0


def test_embed_uses_ollama_when_available(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.embed.embed_ollama",
        return_value=np.array([1.0, 2.0, 3.0], dtype=np.float32),
    )
    v = embed("hello", model="nomic-embed-text")
    assert v.shape[0] == 3
    np.testing.assert_allclose(v, [1.0, 2.0, 3.0])
