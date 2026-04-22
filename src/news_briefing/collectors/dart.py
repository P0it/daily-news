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
    date: str,  # YYYYMMDD
    *,
    page_count: int = 100,
    timeout: int = 15,
) -> list[CollectedItem]:
    if not api_key:
        log.warning("DART_API_KEY 없음, DART 수집 스킵")
        return []
    try:
        resp = requests.get(
            DART_LIST_URL,
            params={
                "crtfc_key": api_key,
                "bgn_de": date,
                "end_de": date,
                "page_no": 1,
                "page_count": page_count,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return parse_dart_response(resp.json())
    except Exception as e:
        log.error("DART 수집 실패: %s", e)
        return []
