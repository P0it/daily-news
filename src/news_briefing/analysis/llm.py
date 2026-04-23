"""LLM 호출 래퍼. Claude Code CLI 주 엔진, Ollama 보조 (DECISIONS #2).

절대 anthropic SDK 직접 호출 금지 (P2).
`_call_claude` / `_call_ollama` 는 **prompt 를 그대로** 전달한다 (system 덧붙이지 않음).
호출자(summarize, RAG, themes 등)가 자신의 프롬프트를 온전히 구성해서 넘겨야 한다.
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
import subprocess
import tempfile

from news_briefing.storage.cache import cache_get, cache_put

log = logging.getLogger(__name__)


def _resolve(cmd: str) -> str:
    """PATH 에서 실행 파일 전체 경로 찾기. Windows `.cmd`/`.bat` 확장자 지원."""
    return shutil.which(cmd) or cmd


SUMMARIZE_TASK = "summarize"
SUMMARIZE_SYSTEM = (
    "너는 금융·경제 뉴스 요약가다. 주어진 공시·기사 제목 또는 본문을 "
    "2줄 이내 한국어로 요약한다. 규칙: "
    "① 매수/매도 권유·목표가·확률 예측 금지 (예: '매수하세요', '오를 가능성 70%'). "
    "② '~요'체 존댓말. ③ 느낌표 금지. "
    "④ 이벤트의 통상적 해석만 기술하고 투자 판단은 사용자에게 맡긴다."
)

TRANSLATE_NEWS_TASK = "translate_news_ko"
TRANSLATE_NEWS_SYSTEM = (
    "아래 영문 AI/IT 뉴스의 제목을 자연스러운 한국어로 번역하고, "
    "본문을 2줄 이내 한국어로 요약한다. "
    "고유명사(제품명·회사명·모델명)는 원문 유지, '~요'체 존댓말, 느낌표 금지. "
    "응답은 정확히 두 줄로만 작성한다. "
    "첫째 줄: TITLE: 로 시작하고 이어서 번역된 한국어 제목. "
    "둘째 줄: SUMMARY: 로 시작하고 이어서 한국어 요약. "
    "인사·설명·마크다운·추가 줄 금지. 곧바로 번역·요약 결과만 출력한다."
)


def _call_claude(prompt: str, timeout: int = 45) -> str:
    """Claude CLI 를 호출해 prompt 를 그대로 전달. stdout 반환.

    Claude Code CLI 는 CWD 의 CLAUDE.md 를 자동으로 읽어 system prompt 화 한다.
    RAG/요약 등 일반 LLM 호출에선 이 context 가 오염이 되므로,
    **임시 디렉토리에서 실행**해 프로젝트 CLAUDE.md 영향을 차단한다.

    Windows `.cmd` wrapper 는 개행이 포함된 argv 를 제대로 전달하지 못하므로
    prompt 는 **stdin 으로 전달** 한다. (argv 경로 사용 시 긴 한글/다줄 prompt 에서
    본문이 잘려 LLM 이 "기사가 포함되어 있지 않아요" 로 응답하는 버그 회피.)
    """
    with tempfile.TemporaryDirectory(prefix="news_briefing_llm_") as tmpdir:
        result = subprocess.run(
            [_resolve("claude"), "-p", "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            cwd=tmpdir,
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude cli returncode={result.returncode} stderr={result.stderr}"
        )
    return (result.stdout or "").strip()


def _call_ollama(prompt: str, model: str, timeout: int = 60) -> str:
    """Ollama 를 호출해 prompt 를 그대로 전달. stdout 반환."""
    result = subprocess.run(
        [_resolve("ollama"), "run", model, prompt],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ollama returncode={result.returncode}")
    return (result.stdout or "").strip()


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

    prompt = f"{SUMMARIZE_SYSTEM}\n\n---\n\n{input_text}"

    try:
        output = _call_claude(prompt)
        cache_put(conn, SUMMARIZE_TASK, input_text, output, "claude-cli")
        return output
    except Exception as e:
        log.warning("claude cli 호출 실패: %s", e)

    if ollama_enabled:
        try:
            output = _call_ollama(prompt, ollama_model)
            cache_put(
                conn, SUMMARIZE_TASK, input_text, output, f"ollama:{ollama_model}"
            )
            return output
        except Exception as e:
            log.error("ollama 호출 실패: %s", e)

    return ""


def _parse_title_summary(output: str) -> tuple[str, str]:
    """'TITLE: ... / SUMMARY: ...' 출력 파싱. 실패 시 ('', '')."""
    title_ko = ""
    summary_ko = ""
    for line in output.splitlines():
        s = line.strip()
        if s.upper().startswith("TITLE:"):
            title_ko = s.split(":", 1)[1].strip()
        elif s.upper().startswith("SUMMARY:"):
            summary_ko = s.split(":", 1)[1].strip()
    return title_ko, summary_ko


def translate_news_ko(
    conn: sqlite3.Connection,
    title: str,
    body: str = "",
    *,
    ollama_enabled: bool = False,
    ollama_model: str = "qwen2.5:14b",
) -> tuple[str, str]:
    """영문 AI/IT 뉴스 → (한국어 제목, 한국어 2줄 요약). 캐시 지원.

    실패 시 ('', '') 반환하고 호출자가 원본 제목을 유지.
    """
    cache_key = f"{title}\n---\n{body[:500]}"  # body 길이 제한으로 캐시 키 안정화
    cached = cache_get(conn, TRANSLATE_NEWS_TASK, cache_key)
    if cached is not None:
        return _parse_title_summary(cached)

    prompt = (
        f"{TRANSLATE_NEWS_SYSTEM}\n\n---\n\n"
        f"제목: {title}\n본문: {body or '(본문 없음)'}"
    )

    try:
        output = _call_claude(prompt)
        cache_put(conn, TRANSLATE_NEWS_TASK, cache_key, output, "claude-cli")
        return _parse_title_summary(output)
    except Exception as e:
        log.warning("translate_news_ko claude 실패: %s", e)

    if ollama_enabled:
        try:
            output = _call_ollama(prompt, ollama_model)
            cache_put(
                conn,
                TRANSLATE_NEWS_TASK,
                cache_key,
                output,
                f"ollama:{ollama_model}",
            )
            return _parse_title_summary(output)
        except Exception as e:
            log.error("translate_news_ko ollama 실패: %s", e)

    return ("", "")
