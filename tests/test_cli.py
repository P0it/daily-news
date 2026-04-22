from __future__ import annotations

from news_briefing.cli import main


def test_cli_no_args_prints_help(capsys, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = main([])
    captured = capsys.readouterr()
    assert rc != 0
    assert "morning" in captured.out or "morning" in captured.err


def test_cli_status_exits_zero(capsys, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = main(["status"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "뉴스 브리핑" in out or "Status" in out or "news" in out.lower()


def test_cli_morning_dry_run_invokes_orchestrator(mocker, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fake_result = mocker.MagicMock(
        new_items=0, signal_count=0, news_count=0, sent_kakao=False
    )
    fake_result.digest_path.name = "2026-04-22.txt"
    mock_run = mocker.patch("news_briefing.cli.run_morning", return_value=fake_result)
    rc = main(["morning", "--dry-run"])
    assert rc == 0
    assert mock_run.call_count == 1
    assert mock_run.call_args.kwargs["dry_run"] is True
