from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from news_briefing.config import Config
from news_briefing.orchestrator import run_morning


def _cfg(tmp_path: Path) -> Config:
    data = tmp_path / "data"
    digests = data / "digests"
    public_briefings = tmp_path / "frontend" / "public" / "briefings"
    return Config(
        dart_api_key="",
        discord_webhook_url="",
        supabase_url="https://example.supabase.co",
        supabase_service_key="svc",
        data_dir=data,
        digests_dir=digests,
        ollama_enabled=False,
        ollama_model="",
        ollama_embed_model="nomic-embed-text",
        public_briefings_dir=public_briefings,
        vercel_base_url="https://news-briefing.vercel.app",
        vercel_deploy_hook_url="",
        edgar_user_agent="",
        fmp_api_key="",
    )


def _patch_all(mocker):
    """모든 수집기 + DB 의존성을 mock 해 외부 호출 없이 파이프라인을 돌린다."""
    for fn in (
        "fetch_dart_list",
        "fetch_all_rss",
        "fetch_all_edgar",
        "fetch_macro",
        "fetch_research_reports",
        "fetch_krx_etf",
        "fetch_gov_contracts",
        "fetch_insider_clusters",
        "fetch_institutional_13f",
        "fetch_congress_trades",
        "fetch_fda_approvals",
        "fetch_press_wires",
        "fetch_analyst_ratings",
    ):
        mocker.patch(f"news_briefing.orchestrator.{fn}", return_value=[])

    mocker.patch("news_briefing.orchestrator.get_client")
    mocker.patch("news_briefing.storage.cleanup.run_cleanup")
    # seen 필터: 입력 pair 를 모두 미열람으로 통과
    mocker.patch(
        "news_briefing.orchestrator.batch_filter_unseen", side_effect=lambda conn, pairs: pairs
    )
    mocker.patch("news_briefing.orchestrator.batch_mark_seen")
    mocker.patch("news_briefing.orchestrator.build_phase_map", return_value={})
    # 후처리(Supabase·picks 히스토리·RAG)는 외부 의존 — 모두 차단
    mocker.patch("news_briefing.storage.briefings.upsert_briefing")
    mocker.patch(
        "news_briefing.analysis.picks_tracker.load_briefings_from_supabase", return_value=[]
    )
    mocker.patch("news_briefing.analysis.picks_tracker.update_history")
    mocker.patch("news_briefing.analysis.rag.index_briefing", return_value=0)


def test_dry_run_writes_digest_and_skips_discord(tmp_path: Path, mocker) -> None:
    cfg = _cfg(tmp_path)
    _patch_all(mocker)
    mock_send = mocker.patch("news_briefing.orchestrator._send_discord")

    result = run_morning(cfg, dry_run=True, now=datetime(2026, 6, 15, 6, 0))

    assert mock_send.call_count == 0
    assert result.digest_path.exists()
    assert "2026-06-15.txt" in result.digest_path.name


def test_briefing_json_is_picks_only_schema(tmp_path: Path, mocker) -> None:
    cfg = _cfg(tmp_path)
    _patch_all(mocker)
    mocker.patch("news_briefing.orchestrator._send_discord")

    result = run_morning(cfg, dry_run=True, now=datetime(2026, 6, 15))
    data = json.loads(result.briefing_json_path.read_text(encoding="utf-8"))

    assert data["version"] == 2
    assert set(data["tabs"].keys()) == {"economy"}
    assert "current" not in data["tabs"]
    assert "ai" not in data["tabs"]
    assert "hero" not in data
    assert "hotIssues" in data["tabs"]["economy"]
    assert "signals" not in data["tabs"]["economy"]


def test_discord_message_is_picks_centric(tmp_path: Path, mocker) -> None:
    cfg = _cfg(tmp_path)
    _patch_all(mocker)
    mock_send = mocker.patch("news_briefing.orchestrator._send_discord", return_value=True)

    run_morning(cfg, dry_run=False, now=datetime(2026, 6, 15))

    assert mock_send.call_count == 1
    msg = mock_send.call_args.args[1]
    assert "종목추천" in msg
    assert "scope=foreign" in msg
    assert "tab=ai" not in msg
