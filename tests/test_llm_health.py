"""LLM 실행 환경·실패율 가드 테스트.

launchd 환경에서 `claude` 가 PATH 에 없으면 모든 LLM 호출이 조용히 실패하고
파이프라인은 exit 0 으로 껍데기 브리핑을 발송한다. 이를 막는 가드를 검증한다.
"""

from __future__ import annotations

import pytest

from news_briefing.analysis import llm


@pytest.fixture(autouse=True)
def _reset() -> None:
    llm.reset_llm_stats()


def test_preflight_ok_when_claude_resolvable(mocker) -> None:
    mocker.patch("news_briefing.analysis.llm.shutil.which", return_value="/opt/homebrew/bin/claude")
    assert llm.preflight_claude() is True


def test_preflight_fails_when_claude_missing(mocker) -> None:
    mocker.patch("news_briefing.analysis.llm.shutil.which", return_value=None)
    assert llm.preflight_claude() is False


def test_stats_count_success_and_failure(mocker) -> None:
    mocker.patch("news_briefing.analysis.llm._resolve", side_effect=lambda c: c)
    mocker.patch(
        "news_briefing.analysis.llm.subprocess.run",
        side_effect=FileNotFoundError("No such file or directory: 'claude'"),
    )
    with pytest.raises(FileNotFoundError):
        llm._call_claude("안녕")

    stats = llm.llm_stats()
    assert stats.calls == 1
    assert stats.failures == 1
    assert stats.failure_rate == 1.0


def test_failure_rate_zero_when_no_calls() -> None:
    """호출이 0건이면 실패율은 0 — 0 나눗셈으로 죽지 않는다."""
    stats = llm.llm_stats()
    assert stats.calls == 0
    assert stats.failure_rate == 0.0


def test_healthy_when_failure_rate_below_threshold(mocker) -> None:
    mocker.patch("news_briefing.analysis.llm._resolve", side_effect=lambda c: c)
    mocker.patch("news_briefing.analysis.llm.shutil.which", return_value="/x/claude")
    ok = mocker.MagicMock(returncode=0, stdout="응답", stderr="")
    mocker.patch("news_briefing.analysis.llm.subprocess.run", return_value=ok)
    for _ in range(4):
        llm._call_claude("안녕")

    assert llm.llm_stats().failure_rate == 0.0
    assert llm.llm_output_is_trustworthy() is True


def test_untrustworthy_when_most_calls_fail(mocker) -> None:
    """실패율이 임계값을 넘으면 발송을 막을 수 있도록 False 를 반환한다."""
    mocker.patch("news_briefing.analysis.llm._resolve", side_effect=lambda c: c)
    mocker.patch("news_briefing.analysis.llm.shutil.which", return_value="/x/claude")
    mocker.patch(
        "news_briefing.analysis.llm.subprocess.run",
        side_effect=FileNotFoundError("boom"),
    )
    for _ in range(4):
        with pytest.raises(FileNotFoundError):
            llm._call_claude("안녕")

    assert llm.llm_stats().failure_rate == 1.0
    assert llm.llm_output_is_trustworthy() is False


def test_untrustworthy_when_binary_missing_even_without_calls(mocker) -> None:
    """호출 전이라도 실행 파일 자체가 없으면 신뢰할 수 없다."""
    mocker.patch("news_briefing.analysis.llm.shutil.which", return_value=None)
    assert llm.llm_output_is_trustworthy() is False
