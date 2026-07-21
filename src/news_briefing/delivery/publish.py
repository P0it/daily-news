"""브리핑 산출물을 git 에 커밋·푸시해 Vercel 배포를 트리거한다.

프론트엔드는 `output: 'export'` static export 라 `public/briefings/*.json` 을
**빌드 시점에 구워 넣는다**. 따라서 파이프라인이 파일을 로컬에만 쓰면 사이트는
갱신되지 않는다. push 자체가 Vercel 재배포를 트리거하므로 deploy hook 은 불필요.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

# 브리핑 실행이 만들어내는 산출물만 스테이징한다. `git add -A` 로 넓게 잡으면
# 작업 중이던 소스 변경까지 자동 커밋되어 의도치 않은 배포가 나간다.
PUBLISH_PATHS = (
    "frontend/public/briefings",
    "frontend/public/picks_history.json",
)

_TIMEOUT = 60


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        check=False,
        # 자격 증명이 없을 때 비대화형 환경(launchd)에서 입력 대기로 멈추지 않게 한다.
        env={
            "GIT_TERMINAL_PROMPT": "0",
            "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
            "HOME": str(Path.home()),
        },
    )


def publish_briefing(repo_root: Path, date: str) -> bool:
    """브리핑 산출물을 커밋·푸시. 성공 시 True.

    실패해도 예외를 밖으로 내보내지 않는다 — 브리핑 자체는 이미 만들어졌고,
    배포 실패가 파이프라인 전체를 죽일 이유는 없다 (에러 처리 원칙).
    변경이 없으면 빈 커밋을 만들지 않고 False 를 반환한다.
    """
    try:
        add = _git(repo_root, "add", "--", *PUBLISH_PATHS)
        if add.returncode != 0:
            log.error("git add 실패: %s", add.stderr.strip()[:300])
            return False

        status = _git(repo_root, "status", "--porcelain", "--", *PUBLISH_PATHS)
        if not status.stdout.strip():
            log.info("브리핑 산출물에 변경 없음 — 커밋 건너뜀")
            return False

        commit = _git(repo_root, "commit", "-m", f"chore(data): 브리핑·picks 데이터 갱신 ({date})")
        if commit.returncode != 0:
            log.error("git commit 실패: %s", commit.stderr.strip()[:300])
            return False

        push = _git(repo_root, "push")
        if push.returncode != 0:
            log.error("git push 실패 (커밋은 로컬에 남음): %s", push.stderr.strip()[:300])
            return False

        log.info("브리핑 push 완료 — Vercel 재배포 트리거됨 (%s)", date)
        return True
    except Exception as e:
        log.error("브리핑 publish 실패: %s", e)
        return False
