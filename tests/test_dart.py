from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from news_briefing.collectors.dart import fetch_dart_list, parse_dart_response


def test_parse_dart_response_returns_collected_items(fixtures_dir: Path) -> None:
    data = json.loads((fixtures_dir / "dart_list.json").read_text(encoding="utf-8"))
    items = parse_dart_response(data)
    assert len(items) == 3
    samsung = items[0]
    assert samsung.source == "dart"
    assert samsung.ext_id == "20260422000001"
    assert samsung.company == "삼성전자"
    assert samsung.company_code == "005930"
    assert samsung.title == "자기주식취득결정"
    assert "dart.fss.or.kr" in samsung.url


def test_parse_dart_response_handles_empty_list() -> None:
    items = parse_dart_response({"status": "000", "list": []})
    assert items == []


def test_parse_dart_response_handles_no_data_status() -> None:
    """DART 013 = '조회된 데이터가 없습니다' 는 에러가 아니라 빈 결과."""
    items = parse_dart_response({"status": "013", "message": "조회된 데이터가 없습니다."})
    assert items == []


def test_parse_dart_response_rejects_unknown_error() -> None:
    with pytest.raises(RuntimeError, match="DART"):
        parse_dart_response({"status": "999", "message": "알 수 없는 오류"})


def test_fetch_dart_list_makes_http_request(mocker) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "000", "list": []}
    mock_resp.raise_for_status = MagicMock()
    mock_get = mocker.patch(
        "news_briefing.collectors.dart.requests.get", return_value=mock_resp
    )
    result = fetch_dart_list(api_key="k", date="20260422")
    assert result == []
    args, kwargs = mock_get.call_args
    assert "opendart.fss.or.kr" in args[0]
    assert kwargs["params"]["crtfc_key"] == "k"
    assert kwargs["params"]["bgn_de"] == "20260422"
    assert kwargs["params"]["end_de"] == "20260422"


def test_fetch_dart_list_empty_key_returns_empty_without_request(mocker) -> None:
    """DART_API_KEY 가 비어 있으면 HTTP 호출 없이 빈 리스트."""
    mock_get = mocker.patch("news_briefing.collectors.dart.requests.get")
    result = fetch_dart_list(api_key="", date="20260422")
    assert result == []
    assert mock_get.call_count == 0
