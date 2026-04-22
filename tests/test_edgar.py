from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from news_briefing.collectors.edgar import (
    fetch_edgar_form4,
    parse_edgar_atom,
)


def test_parse_form4_returns_collected_items(fixtures_dir: Path) -> None:
    content = (fixtures_dir / "edgar_form4.atom").read_text(encoding="utf-8")
    items = parse_edgar_atom(content, form_type="4")
    assert len(items) == 2
    nvda = items[0]
    assert nvda.source == "edgar"
    assert "NVIDIA" in nvda.company
    assert nvda.company_code == "0001045810"
    assert nvda.url.startswith("https://www.sec.gov/")
    assert nvda.extra.get("form_type") == "4"


def test_parse_8k_extracts_item_numbers(fixtures_dir: Path) -> None:
    content = (fixtures_dir / "edgar_8k.atom").read_text(encoding="utf-8")
    items = parse_edgar_atom(content, form_type="8-K")
    assert items[0].extra.get("form_type") == "8-K"
    assert "2.02" in items[0].extra.get("items", "")


def test_parse_empty_returns_empty_list() -> None:
    empty_feed = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    assert parse_edgar_atom(empty_feed, form_type="4") == []


def test_parse_malformed_returns_empty() -> None:
    assert parse_edgar_atom("not xml", form_type="4") == []


def test_fetch_form4_sends_user_agent(mocker) -> None:
    mock_resp = MagicMock()
    mock_resp.text = (
        '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    )
    mock_resp.raise_for_status = MagicMock()
    mock_get = mocker.patch(
        "news_briefing.collectors.edgar.requests.get", return_value=mock_resp
    )
    fetch_edgar_form4(user_agent="Test Agent test@example.com")
    args, kwargs = mock_get.call_args
    assert "cgi-bin/browse-edgar" in args[0]
    assert kwargs["params"]["type"] == "4"
    assert "Test Agent" in kwargs["headers"]["User-Agent"]


def test_fetch_without_user_agent_skips(mocker) -> None:
    mock_get = mocker.patch("news_briefing.collectors.edgar.requests.get")
    items = fetch_edgar_form4(user_agent="")
    assert items == []
    assert mock_get.call_count == 0
