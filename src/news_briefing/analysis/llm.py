"""LLM 호출 래퍼. Claude Code CLI 주 엔진, Ollama 보조 (DECISIONS #2).

절대 anthropic SDK 직접 호출 금지 (P2).
`_call_claude` / `_call_ollama` 는 **prompt 를 그대로** 전달한다 (system 덧붙이지 않음).
호출자(summarize, RAG, themes 등)가 자신의 프롬프트를 온전히 구성해서 넘겨야 한다.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass

from news_briefing.storage.cache import cache_get, cache_put

log = logging.getLogger(__name__)


def _resolve(cmd: str) -> str:
    """PATH 에서 실행 파일 전체 경로 찾기. Windows `.cmd`/`.bat` 확장자 지원."""
    return shutil.which(cmd) or cmd


# LLM 호출이 전부 실패해도 각 호출부가 예외를 삼키고 WARNING 만 남기므로,
# 파이프라인은 exit 0 으로 끝나고 요약·번역이 텅 빈 브리핑이 발송된다.
# (실제 사고: launchd 의 PATH 에 Homebrew 가 없어 `claude` 를 못 찾음.)
# 호출 결과를 집계해 발송 직전에 "이 브리핑을 믿을 수 있는가" 를 판단한다.
MAX_LLM_FAILURE_RATE = 0.5


@dataclass
class LLMStats:
    """한 번의 파이프라인 실행 동안 누적된 Claude CLI 호출 통계."""

    calls: int = 0
    failures: int = 0

    @property
    def failure_rate(self) -> float:
        """실패 비율. 호출이 0건이면 0.0 (0 나눗셈 방지)."""
        if self.calls == 0:
            return 0.0
        return self.failures / self.calls


_stats = LLMStats()


def llm_stats() -> LLMStats:
    """현재 누적된 호출 통계를 반환."""
    return _stats


def reset_llm_stats() -> None:
    """통계를 초기화. 파이프라인 시작 시·테스트 격리용."""
    global _stats
    _stats = LLMStats()


def preflight_claude() -> bool:
    """`claude` 실행 파일이 PATH 에서 발견되는지 확인.

    launchd 는 로그인 셸 PATH 를 물려받지 않아 여기서 걸리는 경우가 있다.
    호출 한 번 없이도 환경 문제를 조기에 감지하기 위한 사전 점검.
    """
    return shutil.which("claude") is not None


def llm_output_is_trustworthy() -> bool:
    """LLM 산출물을 신뢰할 수 있는지 판단. 발송 여부 결정에 사용.

    실행 파일이 아예 없거나, 실패율이 `MAX_LLM_FAILURE_RATE` 를 넘으면 False.
    """
    if not preflight_claude():
        return False
    return _stats.failure_rate <= MAX_LLM_FAILURE_RATE


SUMMARIZE_TASK = "summarize"
SUMMARIZE_SYSTEM = (
    "너는 금융·경제 뉴스 요약가다. 주어진 공시·기사 제목 또는 본문을 "
    "2줄 이내 한국어로 요약한다. 규칙: "
    "① 매수/매도 권유·목표가·확률 예측 금지 (예: '매수하세요', '오를 가능성 70%'). "
    "② 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓). ③ 느낌표 금지. "
    "④ 이벤트의 통상적 해석만 기술하고 투자 판단은 사용자에게 맡긴다. "
    "⑤ 기업명·제품명·브랜드명 등 고유명사는 반드시 원문(영문) 그대로 표기한다 "
    "(예: Anthropic → Anthropic, NVIDIA → NVIDIA, 음역 금지)."
)

TRANSLATE_NEWS_TASK = "translate_news_ko"
TRANSLATE_NEWS_SYSTEM = (
    "아래 영문 AI/IT 뉴스의 제목을 자연스러운 한국어로 번역하고, "
    "본문을 2줄 이내 한국어로 요약한다. "
    "고유명사(기업명·제품명·모델명)는 원문(영문) 그대로 표기한다. 음역 금지. 느낌표 금지. "
    "제목: 신문 헤드라인 형식 (~다 체 또는 명사형 종결). '~요'체 절대 금지. "
    "요약: 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓). "
    "응답은 정확히 두 줄로만 작성한다. "
    "첫째 줄: TITLE: 로 시작하고 이어서 번역된 한국어 제목. "
    "둘째 줄: SUMMARY: 로 시작하고 이어서 한국어 요약. "
    "인사·설명·마크다운·추가 줄 금지. 곧바로 번역·요약 결과만 출력한다."
)


def _call_claude(prompt: str, timeout: int = 45, model: str | None = None) -> str:
    """Claude CLI 를 호출해 prompt 를 그대로 전달. stdout 반환.

    Claude Code CLI 는 CWD 의 CLAUDE.md 를 자동으로 읽어 system prompt 화 한다.
    RAG/요약 등 일반 LLM 호출에선 이 context 가 오염이 되므로,
    **임시 디렉토리에서 실행**해 프로젝트 CLAUDE.md 영향을 차단한다.

    Windows `.cmd` wrapper 는 개행이 포함된 argv 를 제대로 전달하지 못하므로
    prompt 는 **stdin 으로 전달** 한다. (argv 경로 사용 시 긴 한글/다줄 prompt 에서
    본문이 잘려 LLM 이 "기사가 포함되어 있지 않아요" 로 응답하는 버그 회피.)

    model: "sonnet"|"opus" 등 별칭 또는 전체 모델명. None 이면 사용자 기본 모델.
        요약·번역 등 가벼운 작업은 "sonnet" 으로 내려 속도를 확보하고,
        hot_issues 같은 추론 작업은 "opus" 로 품질을 사수한다.
    """
    cmd = [_resolve("claude"), "-p", "--output-format", "text"]
    if model:
        cmd += ["--model", model]
    _stats.calls += 1
    try:
        with tempfile.TemporaryDirectory(prefix="news_briefing_llm_") as tmpdir:
            result = subprocess.run(
                cmd,
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
                f"claude cli returncode={result.returncode} stderr={result.stderr[:500]}"
            )
        output = (result.stdout or "").strip()
        if not output:
            stderr_hint = (result.stderr or "").strip()[:300]
            raise RuntimeError(f"claude cli returned empty stdout (stderr={stderr_hint!r})")
    except Exception:
        # 호출부가 예외를 삼키더라도 실패 사실은 통계에 남겨야 발송 가드가 동작한다.
        _stats.failures += 1
        raise
    return output


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


_SUMMARIZE_BATCH_SYSTEM = (
    "너는 금융·경제 뉴스 요약가다. 아래 번호가 붙은 기사 제목들을 각각 2줄 이내 한국어로 요약한다.\n"
    "규칙: ① 매수/매도 권유·목표가·확률 예측 금지. ② 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓). ③ 느낌표 금지.\n"
    "④ 이벤트의 통상적 해석만 기술하고 투자 판단은 사용자에게 맡긴다.\n"
    "⑤ 기업명·제품명·브랜드명 등 고유명사는 원문(영문) 그대로 표기한다 (음역 금지).\n\n"
    "반드시 JSON 배열만 반환. 마크다운·설명 텍스트 없이 배열 그대로.\n"
    '[{"idx": 1, "summary": "..."}, {"idx": 2, "summary": "..."}, ...]'
)

_TRANSLATE_BATCH_SYSTEM = (
    "아래 번호가 붙은 영문 AI/IT 뉴스들의 제목을 한국어로 번역하고 본문을 2줄 이내로 요약한다.\n"
    "규칙: ① 고유명사(기업명·제품명·모델명)는 원문(영문) 그대로 표기한다. 음역 금지.\n"
    "② 제목(title_ko): 신문 헤드라인 형식 (~다 체 또는 명사형 종결). '~요'체 절대 금지.\n"
    "③ 요약(summary_ko): 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓). ④ 느낌표 금지.\n\n"
    "반드시 JSON 배열만 반환. 마크다운·설명 텍스트 없이 배열 그대로.\n"
    '[{"idx": 1, "title_ko": "...", "summary_ko": "..."}, ...]'
)


def summarize_batch(
    conn: sqlite3.Connection,
    items: list[tuple[str, str]],
    *,
    batch_size: int = 15,
    timeout: int = 180,
    ollama_enabled: bool = False,
    ollama_model: str = "qwen2.5:14b",
) -> dict[str, str]:
    """기사 제목 목록을 배치로 요약. 캐시 히트 항목은 LLM 호출 없이 반환.

    items: [(ext_id, text), ...]
    반환: {ext_id: summary_text}
    """
    result: dict[str, str] = {}
    uncached: list[tuple[str, str]] = []

    for ext_id, text in items:
        cached = cache_get(conn, SUMMARIZE_TASK, text)
        if cached is not None:
            result[ext_id] = cached
        else:
            uncached.append((ext_id, text))

    if not uncached:
        return result

    def _call_batch(batch: list[tuple[str, str]]) -> dict[str, str]:
        numbered = "\n".join(f"[{i + 1}] {text}" for i, (_, text) in enumerate(batch))
        prompt = f"{_SUMMARIZE_BATCH_SYSTEM}\n\n---\n\n{numbered}"

        def _parse(raw: str) -> list[dict]:
            raw = raw.strip()
            if raw.startswith("```"):
                raw = "\n".join(
                    l for l in raw.splitlines() if not l.strip().startswith("```")
                ).strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [
                        r for r in parsed if isinstance(r, dict) and "idx" in r and "summary" in r
                    ]
            except Exception:
                pass
            return []

        out: dict[str, str] = {}
        try:
            # 가벼운 요약 작업 → Sonnet 으로 속도 확보 (품질 충분)
            raw = _call_claude(prompt, timeout=timeout, model="sonnet")
            for r in _parse(raw):
                idx = int(r["idx"]) - 1
                if 0 <= idx < len(batch):
                    ext_id, text = batch[idx]
                    summary = str(r["summary"]).strip()
                    cache_put(conn, SUMMARIZE_TASK, text, summary, "claude-cli")
                    out[ext_id] = summary
        except Exception as e:
            log.warning("summarize_batch claude 실패 (batch_size=%d): %s", len(batch), e)
            if ollama_enabled:
                try:
                    raw = _call_ollama(prompt, ollama_model, timeout=timeout)
                    for r in _parse(raw):
                        idx = int(r["idx"]) - 1
                        if 0 <= idx < len(batch):
                            ext_id, text = batch[idx]
                            summary = str(r["summary"]).strip()
                            cache_put(conn, SUMMARIZE_TASK, text, summary, f"ollama:{ollama_model}")
                            out[ext_id] = summary
                except Exception as e2:
                    log.error("summarize_batch ollama 실패: %s", e2)
        return out

    for i in range(0, len(uncached), batch_size):
        batch = uncached[i : i + batch_size]
        result.update(_call_batch(batch))
        log.info("summarize_batch: %d/%d 완료", min(i + batch_size, len(uncached)), len(uncached))

    return result


def translate_batch(
    conn: sqlite3.Connection,
    items: list[tuple[str, str, str]],
    *,
    batch_size: int = 15,
    timeout: int = 180,
    ollama_enabled: bool = False,
    ollama_model: str = "qwen2.5:14b",
) -> dict[str, tuple[str, str]]:
    """영문 AI/IT 뉴스 제목·본문을 배치로 번역+요약. 캐시 히트 항목은 LLM 호출 없이 반환.

    items: [(ext_id, title, body), ...]
    반환: {ext_id: (title_ko, summary_ko)}
    """
    result: dict[str, tuple[str, str]] = {}
    uncached: list[tuple[str, str, str]] = []

    for ext_id, title, body in items:
        cache_key = f"{title}\n---\n{body[:500]}"
        cached = cache_get(conn, TRANSLATE_NEWS_TASK, cache_key)
        if cached is not None:
            result[ext_id] = _parse_title_summary(cached)
        else:
            uncached.append((ext_id, title, body))

    if not uncached:
        return result

    def _call_batch(batch: list[tuple[str, str, str]]) -> dict[str, tuple[str, str]]:
        lines = []
        for i, (_, title, body) in enumerate(batch):
            lines.append(f"[{i + 1}] 제목: {title}\n    본문: {body[:300] or '(없음)'}")
        prompt = f"{_TRANSLATE_BATCH_SYSTEM}\n\n---\n\n" + "\n\n".join(lines)

        def _parse(raw: str) -> list[dict]:
            raw = raw.strip()
            if raw.startswith("```"):
                raw = "\n".join(
                    l for l in raw.splitlines() if not l.strip().startswith("```")
                ).strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [r for r in parsed if isinstance(r, dict) and "idx" in r]
            except Exception:
                pass
            return []

        out: dict[str, tuple[str, str]] = {}
        try:
            # 가벼운 번역+요약 작업 → Sonnet 으로 속도 확보 (품질 충분)
            raw = _call_claude(prompt, timeout=timeout, model="sonnet")
            for r in _parse(raw):
                idx = int(r["idx"]) - 1
                if 0 <= idx < len(batch):
                    ext_id, title, body = batch[idx]
                    title_ko = str(r.get("title_ko") or "").strip()
                    summary_ko = str(r.get("summary_ko") or "").strip()
                    cache_key = f"{title}\n---\n{body[:500]}"
                    # 개별 캐시 포맷(TITLE:/SUMMARY:)으로 저장해 translate_news_ko 와 호환
                    cache_put(
                        conn,
                        TRANSLATE_NEWS_TASK,
                        cache_key,
                        f"TITLE: {title_ko}\nSUMMARY: {summary_ko}",
                        "claude-cli",
                    )
                    out[ext_id] = (title_ko, summary_ko)
        except Exception as e:
            log.warning("translate_batch claude 실패 (batch_size=%d): %s", len(batch), e)
            if ollama_enabled:
                try:
                    raw = _call_ollama(prompt, ollama_model, timeout=timeout)
                    for r in _parse(raw):
                        idx = int(r["idx"]) - 1
                        if 0 <= idx < len(batch):
                            ext_id, title, body = batch[idx]
                            title_ko = str(r.get("title_ko") or "").strip()
                            summary_ko = str(r.get("summary_ko") or "").strip()
                            cache_key = f"{title}\n---\n{body[:500]}"
                            cache_put(
                                conn,
                                TRANSLATE_NEWS_TASK,
                                cache_key,
                                f"TITLE: {title_ko}\nSUMMARY: {summary_ko}",
                                f"ollama:{ollama_model}",
                            )
                            out[ext_id] = (title_ko, summary_ko)
                except Exception as e2:
                    log.error("translate_batch ollama 실패: %s", e2)
        return out

    for i in range(0, len(uncached), batch_size):
        batch = uncached[i : i + batch_size]
        result.update(_call_batch(batch))
        log.info("translate_batch: %d/%d 완료", min(i + batch_size, len(uncached)), len(uncached))

    return result


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
            cache_put(conn, SUMMARIZE_TASK, input_text, output, f"ollama:{ollama_model}")
            return output
        except Exception as e:
            log.error("ollama 호출 실패: %s", e)

    return ""


PICK_RATIONALE_TASK = "pick_rationale"
PICK_RATIONALE_SYSTEM = (
    "너는 개인 투자자를 위한 금융 분석가다. "
    "주어진 공시·리포트 제목과 회사명을 보고, 이 종목이 오늘 주목할 만한 이유를 "
    "2~3문장 한국어로 설명한다. 규칙: "
    "① 자연스러운 한국어 경어체 (에요/예요/해요/거예요 등 — 명사 바로 뒤에 '요'만 단독으로 붙이는 방식 금지. 예: '시그널이요' ✗ → '시그널이에요' ✓). ② 느낌표 금지. ③ 매수·매도 권유 금지. "
    "④ 이 이벤트가 어떤 의미를 가지는지, 시장에서 통상 어떻게 해석되는지 포함. "
    "⑤ 설명만 출력, 인사·마크다운·추가 줄 금지."
)


def pick_rationale(
    conn: sqlite3.Connection,
    company: str,
    headline: str,
    *,
    ollama_enabled: bool = False,
    ollama_model: str = "qwen2.5:14b",
) -> str:
    """공시·리포트 제목 → 왜 오늘 주목할 만한지 2~3문장 설명. 캐시 지원. 실패 시 ''."""
    input_text = f"회사: {company}\n제목: {headline}"
    cached = cache_get(conn, PICK_RATIONALE_TASK, input_text)
    if cached is not None:
        return cached

    prompt = f"{PICK_RATIONALE_SYSTEM}\n\n---\n\n{input_text}"

    try:
        output = _call_claude(prompt)
        cache_put(conn, PICK_RATIONALE_TASK, input_text, output, "claude-cli")
        return output
    except Exception as e:
        log.warning("pick_rationale claude 실패: %s", e)

    if ollama_enabled:
        try:
            output = _call_ollama(prompt, ollama_model)
            cache_put(conn, PICK_RATIONALE_TASK, input_text, output, f"ollama:{ollama_model}")
            return output
        except Exception as e:
            log.error("pick_rationale ollama 실패: %s", e)

    return ""


PICK_FOREIGN_TASK = "pick_foreign_news"
PICK_FOREIGN_SYSTEM = (
    "너는 해외 주식 투자 전문 애널리스트다. "
    "아래 해외 주식·경제 뉴스 헤드라인 목록을 보고, "
    "특정 상장 기업에 관한 투자 시그널이 있는 항목만 선별한다.\n\n"
    "선별 기준:\n"
    "- 실적 발표(earnings), 가이던스, 애널리스트 목표주가 변경, M&A, FDA 승인, 대형 계약 등\n"
    "- 시장 전반(Fed 금리, 유가, 지수 등) 뉴스 → 제외\n"
    "- 특정 기업명이 명확히 등장하지 않으면 → 제외\n\n"
    "결과는 아래 JSON 배열 형식으로만 출력 (마크다운·설명·추가 텍스트 일절 금지):\n"
    '[{"idx":0,"company":"Apple Inc","ticker":"AAPL","score":78,"direction":"positive",'
    '"reason":"2~3문장 한국어 투자 포인트. \'~요\'체. 느낌표 금지. 매수·매도 권유 금지."}]\n\n'
    "score: 55~95 사이 정수 (실적 미스·대형 악재=80+, 실적 비트·계약=75+, 목표가 변경=65+)\n"
    "direction: positive | negative | mixed | neutral\n"
    "선별 항목이 없으면 []"
)


def pick_foreign_news(
    conn: sqlite3.Connection,
    headlines: list[tuple[int, str]],  # (idx, headline) 목록
    *,
    ollama_enabled: bool = False,
    ollama_model: str = "qwen2.5:14b",
    timeout: int = 60,
) -> list[dict]:
    """해외 뉴스 헤드라인 배치 → 기업별 pick 후보 리스트.

    반환값: [{"idx": int, "company": str, "ticker": str,
              "score": int, "direction": str, "reason": str}]
    실패 또는 파싱 오류 시 [].
    """
    if not headlines:
        return []

    # 캐시 키: 제목 목록 전체의 해시 (LLM 호출 비용 절약)
    cache_key = "\n".join(f"{i}|{h}" for i, h in headlines)
    cached = cache_get(conn, PICK_FOREIGN_TASK, cache_key)
    if cached is not None:
        try:
            return json.loads(cached)
        except Exception:
            pass

    numbered = "\n".join(f"[{i}] {h}" for i, h in headlines)
    prompt = f"{PICK_FOREIGN_SYSTEM}\n\n---\n\n{numbered}"

    def _parse(raw: str) -> list[dict]:
        raw = raw.strip()
        # LLM이 ```json ... ``` 블록으로 감싸는 경우 제거
        if raw.startswith("```"):
            raw = "\n".join(
                line for line in raw.splitlines() if not line.strip().startswith("```")
            ).strip()
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return [
                    r
                    for r in result
                    if isinstance(r, dict) and r.get("ticker") and r.get("company")
                ]
        except Exception:
            pass
        return []

    try:
        output = _call_claude(prompt, timeout=timeout)
        parsed = _parse(output)
        cache_put(conn, PICK_FOREIGN_TASK, cache_key, json.dumps(parsed), "claude-cli")
        return parsed
    except Exception as e:
        log.warning("pick_foreign_news claude 실패: %s", e)

    if ollama_enabled:
        try:
            output = _call_ollama(prompt, ollama_model, timeout=timeout)
            parsed = _parse(output)
            cache_put(
                conn, PICK_FOREIGN_TASK, cache_key, json.dumps(parsed), f"ollama:{ollama_model}"
            )
            return parsed
        except Exception as e:
            log.error("pick_foreign_news ollama 실패: %s", e)

    return []


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

    prompt = f"{TRANSLATE_NEWS_SYSTEM}\n\n---\n\n제목: {title}\n본문: {body or '(본문 없음)'}"

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
