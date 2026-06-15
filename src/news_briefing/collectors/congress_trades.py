"""미 의회 의원 주식 거래 공시 수집기.

상·하원 의원의 STOCK Act 거래 신고를 공개 데이터셋에서 수집한다.
정보 우위·정책 연관 종목을 시장보다 먼저 포착하는 선행 지표.

소스는 커뮤니티 미러(GitHub raw JSON)라 가용성 변동이 큼 → 실패 시 조용히 빈 결과.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

_TIMEOUT = 20

# 커뮤니티 미러 (timothycarambat) — 상·하원 전체 거래 집계
_SOURCES: list[tuple[str, str]] = [
    (
        "senate",
        "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json",
    ),
    (
        "house",
        "https://raw.githubusercontent.com/timothycarambat/house-stock-watcher-data/master/data/all_transactions.json",
    ),
]

_BUY_TYPES = ("purchase", "buy")


def _parse_tx_date(raw: str) -> datetime | None:
    """거래 신고 날짜 파싱 (MM/DD/YYYY 또는 YYYY-MM-DD)."""
    raw = (raw or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _amount_score(amount_raw: str) -> int:
    """거래 금액 구간 문자열 → 점수. 대형 거래일수록 신호 강도 ↑."""
    a = (amount_raw or "").lower()
    if any(k in a for k in ("1,000,001", "5,000,000", "25,000,000", "50,000,000")):
        return 80
    if "500,001" in a or "250,001" in a:
        return 75
    return 65


def fetch_congress_trades(lookback_days: int = 7, *, limit: int = 40) -> list[CollectedItem]:
    """최근 lookback_days 내 의원 매수 거래(티커 보유분) 반환."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=lookback_days)
    items: list[CollectedItem] = []

    for chamber, url in _SOURCES:
        try:
            resp = requests.get(
                url, timeout=_TIMEOUT, headers={"User-Agent": "news-briefing"}
            )
            resp.raise_for_status()
            rows = resp.json()
        except Exception as e:
            log.warning("congress_trades(%s) 조회 실패 (건너뜀): %s", chamber, e)
            continue

        for row in rows:
            ticker = str(row.get("ticker", "")).strip().upper()
            if not ticker or ticker in ("--", "N/A"):
                continue
            tx_type = str(row.get("type", "")).strip().lower()
            if not any(b in tx_type for b in _BUY_TYPES):
                continue
            tx_date = _parse_tx_date(str(row.get("transaction_date", "")))
            if tx_date is None or tx_date < cutoff:
                continue

            member = str(row.get("senator") or row.get("representative") or "").strip()
            amount = str(row.get("amount", "")).strip()
            score = _amount_score(amount)
            disclosure_id = str(
                row.get("ptr_link") or row.get("disclosure_date") or ""
            ).strip()

            headline = f"[의회 매수] {member or chamber} — {ticker} 매수 ({amount})"
            items.append(
                CollectedItem(
                    source="congress_trades",
                    ext_id=f"cong_{chamber}_{ticker}_{tx_date.strftime('%Y%m%d')}_{disclosure_id[-12:]}",
                    kind="disclosure",
                    title=headline,
                    url=str(row.get("ptr_link", "")) or "https://www.capitoltrades.com/",
                    published_at=tx_date,
                    body=f"{member or chamber} 의원이 {ticker} 를 매수 신고했어요 ({amount}).",
                    company=ticker,
                    company_code=ticker,
                    extra={
                        "scope": "foreign",
                        "chamber": chamber,
                        "member": member,
                        "amount_range": amount,
                        "pre_scored": score,
                    },
                )
            )

    # 최신순 정렬 후 상한
    items.sort(key=lambda i: i.published_at, reverse=True)
    items = items[:limit]
    log.info("congress_trades: %d건 수집", len(items))
    return items
