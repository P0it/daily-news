"""해외 애널리스트 등급변경·목표가 수집기 (Financial Modeling Prep).

국내 증권사 리포트(research.py)의 해외판. 등급 상향·신규 커버리지는
종목 재평가의 선행 시그널이다.

FMP 무료키(일 250회)를 .env 의 FMP_API_KEY 로 받는다. 키가 없거나
엔드포인트가 플랜 제한이면 조용히 빈 결과 → 나머지 파이프라인은 정상 진행.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

_TIMEOUT = 15
_UPGRADES_URL = "https://financialmodelingprep.com/api/v3/upgrades-downgrades-rss-feed"

# action(소문자) → (점수, 방향)
_ACTION_SCORE: dict[str, tuple[int, str]] = {
    "upgrade": (80, "positive"),
    "initialise": (75, "positive"),
    "initialize": (75, "positive"),
    "hold": (60, "neutral"),
    "maintain": (60, "neutral"),
    "downgrade": (78, "negative"),
}


def _parse_date(raw: str) -> datetime:
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.now(UTC)


def fetch_analyst_ratings(api_key: str, *, pages: int = 1) -> list[CollectedItem]:
    """최신 애널리스트 등급변경 수집. api_key 없으면 빈 결과."""
    if not api_key:
        log.info("FMP_API_KEY 없음, analyst_ratings 수집 스킵")
        return []

    items: list[CollectedItem] = []
    for page in range(pages):
        try:
            resp = requests.get(
                _UPGRADES_URL,
                params={"page": page, "apikey": api_key},
                timeout=_TIMEOUT,
            )
            if resp.status_code in (401, 403):
                log.warning(
                    "FMP 접근 거부(%s) — 무료 플랜 제한 가능, analyst 스킵", resp.status_code
                )
                return items
            resp.raise_for_status()
            rows = resp.json()
        except Exception as e:
            log.warning("analyst_ratings 조회 실패 (건너뜀): %s", e)
            break

        if not isinstance(rows, list) or not rows:
            break

        for row in rows:
            symbol = str(row.get("symbol", "")).strip().upper()
            if not symbol:
                continue
            action = str(row.get("action", "")).strip().lower()
            score, direction = _ACTION_SCORE.get(action, (70, "mixed"))
            new_grade = str(row.get("newGrade", "")).strip()
            prev_grade = str(row.get("previousGrade", "")).strip()
            firm = str(row.get("gradingCompany", "")).strip()
            published = _parse_date(str(row.get("publishedDate", "")))

            grade_part = f"{prev_grade}→{new_grade}" if prev_grade else new_grade
            headline = f"[애널 {action or '의견'}] {symbol} — {firm} {grade_part}".strip()
            items.append(
                CollectedItem(
                    source="analyst",
                    ext_id=f"analyst_{symbol}_{published.strftime('%Y%m%d')}_{firm[:10]}",
                    kind="disclosure",
                    title=headline,
                    url=str(row.get("newsURL", "")).strip(),
                    published_at=published,
                    body=str(row.get("newsTitle", "")).strip(),
                    company=symbol,
                    company_code=symbol,
                    extra={
                        "scope": "foreign",
                        "firm": firm,
                        "action": action,
                        "new_grade": new_grade,
                        "previous_grade": prev_grade,
                        "pre_scored": score,
                        "direction": direction,
                    },
                )
            )

    log.info("analyst_ratings: %d건 수집", len(items))
    return items
