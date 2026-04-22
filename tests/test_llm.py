from __future__ import annotations

import sqlite3
import subprocess

from news_briefing.analysis.llm import summarize
from news_briefing.storage.db import init_schema


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["claude"], returncode=returncode, stdout=stdout, stderr=""
    )


def test_summarize_calls_claude_cli(memory_db: sqlite3.Connection, mocker) -> None:
    init_schema(memory_db)
    mock_run = mocker.patch(
        "news_briefing.analysis.llm.subprocess.run",
        return_value=_completed(stdout="삼성전자가 자사주를 매수합니다.\n주주환원 목적입니다."),
    )
    result = summarize(memory_db, "자사주 취득결정", ollama_enabled=False)
    assert result == "삼성전자가 자사주를 매수합니다.\n주주환원 목적입니다."
    assert mock_run.call_count == 1
    assert mock_run.call_args.args[0][0] == "claude"


def test_summarize_uses_cache_on_second_call(memory_db: sqlite3.Connection, mocker) -> None:
    init_schema(memory_db)
    mock_run = mocker.patch(
        "news_briefing.analysis.llm.subprocess.run",
        return_value=_completed(stdout="캐시될 요약"),
    )
    summarize(memory_db, "입력A", ollama_enabled=False)
    summarize(memory_db, "입력A", ollama_enabled=False)
    assert mock_run.call_count == 1  # 두 번째는 캐시 hit


def test_summarize_falls_back_to_ollama_when_claude_fails(
    memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "claude":
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=45)
        return _completed(stdout="올라마 응답")

    mocker.patch("news_briefing.analysis.llm.subprocess.run", side_effect=fake_run)
    result = summarize(
        memory_db, "입력B", ollama_enabled=True, ollama_model="qwen2.5:14b"
    )
    assert result == "올라마 응답"
    assert calls[0][0] == "claude"
    assert calls[1][0] == "ollama"


def test_summarize_returns_empty_on_total_failure(
    memory_db: sqlite3.Connection, mocker
) -> None:
    init_schema(memory_db)
    mocker.patch(
        "news_briefing.analysis.llm.subprocess.run",
        side_effect=FileNotFoundError("no claude"),
    )
    result = summarize(memory_db, "입력C", ollama_enabled=False)
    assert result == ""
