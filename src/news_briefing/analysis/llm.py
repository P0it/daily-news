"""LLM 호출 래퍼. Claude Code CLI 주 엔진, Ollama 보조 (DECISIONS #2).

절대 anthropic SDK 직접 호출 금지 (P2).
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
import subprocess

from news_briefing.storage.cache import cache_get, cache_put

log = logging.getLogger(__name__)


def _resolve(cmd: str) -> str:
    """PATH 에서 실행 파일 전체 경로 찾기. Windows `.cmd`/`.bat` 확장자 지원.

    찾지 못하면 원래 이름을 반환하고, 실행 단계에서 FileNotFoundError 가 난다.
    """
    return shutil.which(cmd) or cmd

SUMMARIZE_TASK = "summarize"
SUMMARIZE_SYSTEM = (
    "너는 금융·경제 뉴스 요약가다. 주어진 공시·기사 제목 또는 본문을 "
    "2줄 이내 한국어로 요약한다. 규칙: "
    "① 매수/매도 권유·목표가·확률 예측 금지 (예: '매수하세요', '오를 가능성 70%'). "
    "② '~요'체 존댓말. ③ 느낌표 금지. "
    "④ 이벤트의 통상적 해석만 기술하고 투자 판단은 사용자에게 맡긴다."
)


def _call_claude(input_text: str, timeout: int = 45) -> str:
    prompt = f"{SUMMARIZE_SYSTEM}\n\n---\n\n{input_text}"
    result = subprocess.run(
        [_resolve("claude"), "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude cli returncode={result.returncode} stderr={result.stderr}"
        )
    return result.stdout.strip()


def _call_ollama(input_text: str, model: str, timeout: int = 60) -> str:
    prompt = f"{SUMMARIZE_SYSTEM}\n\n---\n\n{input_text}"
    result = subprocess.run(
        [_resolve("ollama"), "run", model, prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ollama returncode={result.returncode}")
    return result.stdout.strip()


def summarize(
    conn: sqlite3.Connection,
    input_text: str,
    *,
    ollama_enabled: bool = False,
    ollama_model: str = "qwen2.5:14b",
) -> str:
    """공시·뉴스 요약. 캐시 히트 시 LLM 호출 없음. 실패 시 빈 문자열."""
    cached = cache_get(conn, SUMMARIZE_TASK, input_text)
    if cached is not None:
        return cached

    try:
        output = _call_claude(input_text)
        cache_put(conn, SUMMARIZE_TASK, input_text, output, "claude-cli")
        return output
    except Exception as e:
        log.warning("claude cli 호출 실패: %s", e)

    if ollama_enabled:
        try:
            output = _call_ollama(input_text, ollama_model)
            cache_put(conn, SUMMARIZE_TASK, input_text, output, f"ollama:{ollama_model}")
            return output
        except Exception as e:
            log.error("ollama 호출 실패: %s", e)

    return ""
