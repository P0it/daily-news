from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from news_briefing.collectors.base import CollectedItem
from news_briefing.config import Config
from news_briefing.orchestrator import run_morning


def _cfg(tmp_path: Path) -> Config:
    data = tmp_path / "data"
    digests = data / "digests"
    public_briefings = tmp_path / "frontend" / "public" / "briefings"
    return Config(
        dart_api_key="",
        discord_webhook_url="",
        data_dir=data,
        digests_dir=digests,
        db_path=data / "briefing.db",
        ollama_enabled=False,
        ollama_model="",
        public_briefings_dir=public_briefings,
        vercel_base_url="https://news-briefing.vercel.app",
        edgar_user_agent="",
        ollama_embed_model="nomic-embed-text",
    )


def _patch_collectors(mocker):
    """새 수집기들을 한 번에 mock."""
    mocker.patch("news_briefing.orchestrator.fetch_all_rss", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_all_edgar", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_macro", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_research_reports", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_krx_etf", return_value=[])
    mocker.patch("news_briefing.orchestrator.summarize", return_value="")


def test_dry_run_writes_digest_file_and_skips_discord(tmp_path: Path, mocker) -> None:
    cfg = _cfg(tmp_path)
    _patch_collectors(mocker)
    mock_send = mocker.patch("news_briefing.orchestrator._send_discord")

    result = run_morning(cfg, dry_run=True, now=datetime(2026, 4, 22, 6, 0))

    assert mock_send.call_count == 0
    assert result.digest_path.exists()
    assert "2026-04-22.txt" in result.digest_path.name


def test_dedup_prevents_double_processing(tmp_path: Path, mocker) -> None:
    cfg = _cfg(tmp_path)
    sample = CollectedItem(
        source="rss:hankyung",
        ext_id="guid-1",
        kind="news",
        title="테스트 기사",
        url="https://x.com",
        published_at=datetime(2026, 4, 22),
    )
    mocker.patch("news_briefing.orchestrator.fetch_all_rss", return_value=[sample])
    mocker.patch("news_briefing.orchestrator.fetch_all_edgar", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_macro", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_research_reports", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_krx_etf", return_value=[])
    mocker.patch("news_briefing.orchestrator.summarize", return_value="요약")
    mocker.patch("news_briefing.orchestrator._send_discord")

    r1 = run_morning(cfg, dry_run=True, now=datetime(2026, 4, 22, 6, 0))
    r2 = run_morning(cfg, dry_run=True, now=datetime(2026, 4, 22, 7, 0))

    assert r1.new_items == 1
    assert r2.new_items == 0  # dedup


def test_run_morning_writes_briefing_json_with_glossary(
    tmp_path: Path, mocker
) -> None:
    cfg = _cfg(tmp_path)
    sample = CollectedItem(
        source="dart",
        ext_id="abc",
        kind="disclosure",
        title="자기주식취득결정",
        url="https://example.com",
        published_at=datetime(2026, 4, 22),
        company="삼성전자",
        company_code="005930",
    )
    mocker.patch("news_briefing.orchestrator.fetch_dart_list", return_value=[sample])
    mocker.patch("news_briefing.orchestrator.fetch_all_rss", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_all_edgar", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_macro", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_research_reports", return_value=[])
    mocker.patch("news_briefing.orchestrator.fetch_krx_etf", return_value=[])
    mocker.patch("news_briefing.orchestrator.summarize", return_value="")
    mocker.patch("news_briefing.orchestrator._send_discord")

    result = run_morning(cfg, dry_run=True, now=datetime(2026, 4, 22))
    assert result.briefing_json_path.exists()
    data = json.loads(result.briefing_json_path.read_text(encoding="utf-8"))
    assert data["date"] == "2026-04-22"
    assert "self_stock_buy" in data["glossary"]
    assert data["glossary"]["self_stock_buy"]["shortLabel"]
    assert data["tabs"]["economy"]["signals"][0]["glossaryTermId"] == "self_stock_buy"


def test_discord_link_includes_tab_ai_and_date(tmp_path: Path, mocker) -> None:
    """Week 5b (DECISIONS #13): default 탭이 AI 로 전환됨."""
    cfg = _cfg(tmp_path)
    _patch_collectors(mocker)
    mock_send = mocker.patch(
        "news_briefing.orchestrator._send_discord", return_value=True
    )
    run_morning(cfg, dry_run=False, now=datetime(2026, 4, 22))
    assert mock_send.call_count == 1
    msg_arg = mock_send.call_args.args[1]
    assert "데일리 브리핑" in msg_arg
    assert "tab=ai" in msg_arg
    assert "date=2026-04-22" in msg_arg
