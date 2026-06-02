"""미국 정부 계약 수주 수집기 (USASpending.gov API).

언론 보도보다 24~72시간 앞서 수주 정보를 포착할 수 있는 선행 지표.
https://api.usaspending.gov/
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

_BASE = "https://api.usaspending.gov/api/v2"
_TIMEOUT = 15

# 관심 NAICS 코드 — 방산, 반도체, 사이버보안, 우주, AI
_TARGET_NAICS = {
    "336411",  # Aircraft Manufacturing
    "336412",  # Aircraft Engine and Engine Parts Manufacturing
    "334413",  # Semiconductor and Related Device Manufacturing
    "334511",  # Search, Detection, Navigation Instruments
    "334220",  # Radio and Television Broadcasting Equipment
    "541330",  # Engineering Services
    "541519",  # Other Computer Related Services
    "541690",  # Other Scientific and Technical Consulting
    "517110",  # Wired Telecommunications Carriers
    "517210",  # Wireless Telecommunications Carriers
    "336992",  # Military Armored Vehicle, Tank, and Tank Component Manufacturing
    "928110",  # National Security
}

# 점수 기준 — 계약 금액 기반
def _score_contract(amount_usd: float) -> int:
    if amount_usd >= 1_000_000_000:
        return 95
    if amount_usd >= 500_000_000:
        return 90
    if amount_usd >= 100_000_000:
        return 85
    if amount_usd >= 50_000_000:
        return 75
    if amount_usd >= 10_000_000:
        return 65
    return 0  # 1천만 달러 미만은 노이즈


def fetch_gov_contracts(
    lookback_days: int = 2,
    min_amount_usd: float = 10_000_000,
) -> list[CollectedItem]:
    """최근 N일 내 주요 정부 계약 수주 목록 반환.

    USASpending.gov Award Search API 사용 (인증 불필요).
    """
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    payload = {
        "filters": {
            "time_period": [{"start_date": start_date, "end_date": end_date, "date_type": "action_date"}],
            "award_type_codes": ["A", "B", "C", "D"],  # 계약 유형만 (그랜트 제외)
            "naics_codes": list(_TARGET_NAICS),
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Description",
            "Awarding Agency",
            "Action Date",
            "NAICS Code",
            "NAICS Description",
            "Last Modified Date",
        ],
        "sort": "Award Amount",
        "order": "desc",
        "limit": 50,
        "page": 1,
    }

    try:
        resp = requests.post(
            f"{_BASE}/search/spending_by_award/",
            json=payload,
            timeout=_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.error("USASpending.gov 조회 실패: %s", e)
        return []

    items: list[CollectedItem] = []
    for row in data.get("results", []):
        amount = float(row.get("Award Amount") or 0)
        if amount < min_amount_usd:
            continue

        score = _score_contract(amount)
        if score == 0:
            continue

        award_id = str(row.get("Award ID", "")).strip()
        recipient = str(row.get("Recipient Name", "")).strip()
        desc = str(row.get("Description", "")).strip()
        agency = str(row.get("Awarding Agency", "")).strip()
        naics_desc = str(row.get("NAICS Description", "")).strip()
        action_date_str = str(row.get("Action Date", "")).strip()

        try:
            action_date = datetime.strptime(action_date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            action_date = now

        amount_m = amount / 1_000_000
        headline = (
            f"[정부계약] {recipient} — ${amount_m:,.0f}M {naics_desc} 계약 수주 ({agency})"
        )
        summary = desc[:300] if desc else f"{agency} 발주, {naics_desc} 분야"

        items.append(
            CollectedItem(
                source="gov_contracts",
                ext_id=f"usg_{award_id}",
                kind="disclosure",
                title=headline,
                url=f"https://www.usaspending.gov/award/{award_id}/",
                published_at=action_date,
                body=summary,
                company=recipient,
                company_code="",
                extra={
                    "scope": "foreign",
                    "amount_usd": amount,
                    "agency": agency,
                    "naics_code": row.get("NAICS Code", ""),
                    "naics_desc": naics_desc,
                    "pre_scored": score,  # 스코어링 모듈 우회용 힌트
                },
            )
        )

    log.info("gov_contracts: %d건 수집 (기준 $%s+)", len(items), f"{min_amount_usd:,.0f}")
    return items
