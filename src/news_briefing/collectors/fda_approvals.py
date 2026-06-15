"""FDA 의약품 승인 수집기 (openFDA API).

신약·적응증 승인은 제약·바이오 종목의 핵심 촉매. 언론 보도보다 공식 데이터가 빠를 때가 많다.
openFDA 는 인증 불필요(1000 req/일). drugsfda.json 에서 최근 승인(status=AP)을 조회한다.
https://open.fda.gov/apis/drug/drugsfda/
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

_BASE = "https://api.fda.gov/drug/drugsfda.json"
_TIMEOUT = 15
_PRE_SCORED = 80


def fetch_fda_approvals(lookback_days: int = 3, *, limit: int = 30) -> list[CollectedItem]:
    """최근 lookback_days 내 FDA 의약품 승인 목록 반환.

    submission_status_date 기준 최신순. sponsor_name 을 회사로 매핑하되
    티커 변환은 후속 LLM·검증 단계에 맡긴다(스폰서명 ≠ 티커).
    """
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=lookback_days)).strftime("%Y%m%d")
    end = now.strftime("%Y%m%d")
    search = (
        f"submissions.submission_status:AP"
        f"+AND+submissions.submission_status_date:[{start}+TO+{end}]"
    )

    try:
        resp = requests.get(
            _BASE,
            params={"search": search, "limit": limit},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 404:
            # openFDA 는 결과 없으면 404 를 반환 — 정상 케이스로 처리
            log.info("fda_approvals: 최근 %d일 승인 없음", lookback_days)
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.error("openFDA 조회 실패: %s", e)
        return []

    items: list[CollectedItem] = []
    for row in data.get("results", []):
        app_no = str(row.get("application_number", "")).strip()
        sponsor = str(row.get("sponsor_name", "")).strip()
        products = row.get("products") or []
        brand = ""
        if products and isinstance(products, list):
            brand = str(products[0].get("brand_name", "")).strip()

        # 최신 승인 제출의 날짜 추출
        approved_at = now
        for sub in row.get("submissions", []) or []:
            if sub.get("submission_status") != "AP":
                continue
            date_str = str(sub.get("submission_status_date", "")).strip()
            try:
                approved_at = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        label = brand or app_no or "신약"
        headline = f"[FDA 승인] {sponsor} — {label} 승인"
        items.append(
            CollectedItem(
                source="fda",
                ext_id=f"fda_{app_no}",
                kind="disclosure",
                title=headline,
                url=f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app_no}",
                published_at=approved_at,
                body=f"{sponsor} 의 {label} 가 FDA 승인을 받았어요.",
                company=sponsor,
                company_code="",
                extra={
                    "scope": "foreign",
                    "app_no": app_no,
                    "brand_name": brand,
                    "pre_scored": _PRE_SCORED,
                },
            )
        )

    log.info("fda_approvals: %d건 수집", len(items))
    return items
