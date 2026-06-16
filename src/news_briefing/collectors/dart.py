"""DART Open API list.json 수집기."""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DART_VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="


def parse_dart_response(data: dict) -> list[CollectedItem]:
    status = data.get("status", "")
    if status != "000":
        # 013 = 조회된 데이터 없음, 이건 빈 결과로 취급
        if status == "013":
            return []
        raise RuntimeError(f"DART API 에러 status={status} message={data.get('message')}")

    items: list[CollectedItem] = []
    for row in data.get("list", []):
        rcept_dt = row.get("rcept_dt", "")
        try:
            published = datetime.strptime(rcept_dt, "%Y%m%d")
        except ValueError:
            published = datetime.now()
        items.append(
            CollectedItem(
                source="dart",
                ext_id=row["rcept_no"],
                kind="disclosure",
                title=row.get("report_nm", ""),
                url=f"{DART_VIEWER_URL}{row['rcept_no']}",
                published_at=published,
                company=row.get("corp_name", ""),
                company_code=row.get("stock_code", ""),
                extra={
                    "corp_cls": row.get("corp_cls", ""),
                    "corp_code": row.get("corp_code", ""),
                },
            )
        )
    return items


def fetch_dart_list(
    api_key: str,
    date: str,  # YYYYMMDD — 조회 시작일(bgn_de)
    *,
    end_date: str | None = None,  # 조회 종료일(end_de), 기본=date (하루 조회)
    page_count: int = 100,
    max_pages: int = 10,  # 페이지당 100건 × 10 = 최대 1000건 (룩백 윈도우 대비)
    timeout: int = 15,
) -> list[CollectedItem]:
    """DART 공시 목록을 [date, end_date] 구간으로 조회한다.

    아침 브리핑은 직전 거래일 공시를 봐야 하므로 호출부에서 며칠짜리 룩백
    윈도우를 넘긴다. 바쁜 날 하루만 100건을 넘기므로 total_page 까지
    페이지네이션해 잘림을 막는다(max_pages 로 상한).
    """
    if not api_key:
        log.warning("DART_API_KEY 없음, DART 수집 스킵")
        return []
    end = end_date or date
    items: list[CollectedItem] = []
    try:
        page = 1
        while page <= max_pages:
            resp = requests.get(
                DART_LIST_URL,
                params={
                    "crtfc_key": api_key,
                    "bgn_de": date,
                    "end_de": end,
                    "page_no": page,
                    "page_count": page_count,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            items.extend(parse_dart_response(data))
            total_page = int(data.get("total_page", 1) or 1)
            if page >= total_page:
                break
            page += 1
    except Exception as e:
        log.error("DART 수집 실패: %s", e)
    return items
