from __future__ import annotations

from datetime import datetime
from pathlib import Path

from news_briefing.collectors.base import CollectedItem
from news_briefing.config import Config
from news_briefing.orchestrator import run_morning


def _cfg(tmp_path: Path) -> Config:
    data = tmp_path / "data"
    digests = data / "digests"
    return Config(
        dart_api_key="",  # 비워둬서 DART HTTP 호출 안 감
        kakao_rest_api_key="",
        kakao_redirect_uri="http://localhost:8080/callback",
        data_dir=data,
        digests_dir=digests,
        db_path=data / "briefing.db",
        tokens_path=tmp_path / ".kakao_tokens.json",
        ollama_enabled=False,
        ollama_model="",
    )


def test_dry_run_writes_digest_file_and_skips_kakao(tmp_path: Path, mocker) -> None:
    cfg = _cfg(tmp_path)
    mocker.patch("news_briefing.orchestrator.fetch_all_rss", return_value=[])
    mocker.patch("news_briefing.orchestrator.summarize", return_value="")
    mock_send = mocker.patch("news_briefing.orchestrator._send_kakao")

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
    mocker.patch("news_briefing.orchestrator.summarize", return_value="요약")
    mocker.patch("news_briefing.orchestrator._send_kakao")

    r1 = run_morning(cfg, dry_run=True, now=datetime(2026, 4, 22, 6, 0))
    r2 = run_morning(cfg, dry_run=True, now=datetime(2026, 4, 22, 7, 0))

    assert r1.new_items == 1
    assert r2.new_items == 0  # dedup
