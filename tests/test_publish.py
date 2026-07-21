"""브리핑 결과 git 커밋·푸시 테스트.

프론트엔드는 static export 라 `public/briefings/*.json` 이 **커밋에 들어가야만**
Vercel 빌드에 반영된다. 파이프라인이 로컬에만 쓰고 끝나면 사이트는 영원히 옛날 데이터다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from news_briefing.delivery.publish import publish_briefing


def _ok(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["git"], returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "boom") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["git"], returncode=1, stdout="", stderr=stderr)


def test_commits_and_pushes_when_changes_exist(mocker) -> None:
    run = mocker.patch(
        "news_briefing.delivery.publish.subprocess.run",
        side_effect=[
            _ok(),  # add
            _ok(" M frontend/public/briefings/2026-07-22.json"),  # status --porcelain
            _ok(),  # commit
            _ok(),  # push
        ],
    )
    assert publish_briefing(Path("/repo"), "2026-07-22") is True

    commands = [c.args[0] for c in run.call_args_list]
    assert commands[0][:3] == ["git", "-C", "/repo"]
    assert "add" in commands[0]
    assert "commit" in commands[2]
    assert "push" in commands[3]


def test_commit_message_includes_date(mocker) -> None:
    run = mocker.patch(
        "news_briefing.delivery.publish.subprocess.run",
        side_effect=[_ok(), _ok(" M x.json"), _ok(), _ok()],
    )
    publish_briefing(Path("/repo"), "2026-07-22")

    commit_cmd = run.call_args_list[2].args[0]
    assert any("2026-07-22" in part for part in commit_cmd)


def test_skips_commit_when_nothing_changed(mocker) -> None:
    """변경이 없으면 빈 커밋을 만들지 않는다 (매일 무의미한 커밋 방지)."""
    run = mocker.patch(
        "news_briefing.delivery.publish.subprocess.run",
        side_effect=[_ok(), _ok("")],  # add, status → 변경 없음
    )
    assert publish_briefing(Path("/repo"), "2026-07-22") is False
    assert run.call_count == 2


def test_returns_false_when_push_fails_without_raising(mocker) -> None:
    """푸시 실패가 파이프라인 전체를 죽이지 않는다 (에러 처리 원칙)."""
    mocker.patch(
        "news_briefing.delivery.publish.subprocess.run",
        side_effect=[_ok(), _ok(" M x.json"), _ok(), _fail("rejected")],
    )
    assert publish_briefing(Path("/repo"), "2026-07-22") is False


def test_returns_false_when_git_missing(mocker) -> None:
    """launchd 환경에서 git 을 못 찾아도 예외를 밖으로 내보내지 않는다."""
    mocker.patch(
        "news_briefing.delivery.publish.subprocess.run",
        side_effect=FileNotFoundError("git"),
    )
    assert publish_briefing(Path("/repo"), "2026-07-22") is False
