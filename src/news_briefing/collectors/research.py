"""네이버 금융 증권사 리서치 리포트 수집기.

리포트 제목의 키워드(상향/하향/신규)에서 목표주가 방향을 추출한다.
목표주가 수치는 제공되지 않으므로 방향 시그널만 반환. LLM 호출 없음.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

BASE_URL = "https://finance.naver.com"
LIST_URL = f"{BASE_URL}/research/company_list.naver"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": BASE_URL,
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 실제 HTML 컬럼 순서 (tbody 없음, table.type_1 직접 tr):
# td[0] 종목명  td[1] 리포트제목  td[2] 증권사  td[3] PDF  td[4] 날짜  td[5] 조회수
_COL_COMPANY = 0
_COL_TITLE = 1
_COL_FIRM = 2
_COL_DATE = 4

DEFAULT_MAX_PAGES = 3


def fetch_research_reports(max_pages: int = DEFAULT_MAX_PAGES) -> list[CollectedItem]:
    """네이버 금융 기업분석 리포트를 수집한다."""
    results: list[CollectedItem] = []
    for page in range(1, max_pages + 1):
        try:
            items = _fetch_page(page)
            if not items:
                break
            results.extend(items)
        except Exception as e:
            log.warning("research page=%d 수집 실패: %s", page, e)
            break
    log.info("research 수집 완료 %d건", len(results))
    return results


def _fetch_page(page: int) -> list[CollectedItem]:
    resp = requests.get(LIST_URL, params={"page": page}, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "euc-kr"
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", class_="type_1")
    if not isinstance(table, Tag):
        log.debug("research table 없음 page=%d", page)
        return []

    results: list[CollectedItem] = []
    for tr in table.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        item = _parse_row(tds)
        if item is not None:
            results.append(item)
    return results


def _parse_row(tds: list[Tag]) -> CollectedItem | None:
    """td 리스트 → CollectedItem. 파싱 실패 시 None."""
    try:
        # 종목명 + 종목코드
        a_stock = tds[_COL_COMPANY].find("a")
        if not isinstance(a_stock, Tag):
            return None
        company = a_stock.get_text(strip=True)
        code_m = re.search(r"code=(\d+)", str(a_stock.get("href", "")))
        stock_code = code_m.group(1) if code_m else ""

        # 리포트 제목 + URL
        a_report = tds[_COL_TITLE].find("a")
        if not isinstance(a_report, Tag):
            return None
        report_title = a_report.get_text(strip=True)
        href = str(a_report.get("href", ""))
        if not href:
            return None
        url = href if href.startswith("http") else BASE_URL + "/research/" + href.lstrip("/")

        # nid 를 ext_id 로 (URL 기반이라 안정적)
        nid_m = re.search(r"nid=(\d+)", href)
        ext_id = f"naver-research-{nid_m.group(1)}" if nid_m else None
        if not ext_id:
            return None

        # 증권사
        firm = tds[_COL_FIRM].get_text(strip=True)

        # 날짜 (YY.MM.DD 형식)
        date_str = tds[_COL_DATE].get_text(strip=True)
        published_at = _parse_date(date_str)

        # 제목 키워드에서 방향 추출 (목표주가 수치 컬럼 없음)
        tp_direction = _direction_from_title(report_title)
        title = f"[{firm}] {company} {tp_direction} — {report_title}"

        return CollectedItem(
            source="research:naver",
            ext_id=ext_id,
            kind="news",
            title=title,
            url=url,
            published_at=published_at,
            company=company,
            company_code=stock_code,
            extra={
                "category": "research",
                "firm": firm,
                "targetPrice": 0,       # 목록에서 제공 안 됨
                "targetPriceChange": 0,
                "targetPricePct": 0.0,
                "tpDirection": tp_direction,
                "reportTitle": report_title,
            },
        )
    except Exception as e:
        log.debug("research row 파싱 실패: %s", e)
        return None


def _parse_date(date_str: str) -> datetime:
    """YY.MM.DD → datetime (UTC). 파싱 실패 시 now."""
    date_str = date_str.strip()
    for fmt in ("%y.%m.%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _direction_from_title(title: str) -> str:
    """리포트 제목에서 목표주가 방향 키워드 추출."""
    if any(k in title for k in ("상향", "↑", "올려", "높여", "올림")):
        return "상향"
    if any(k in title for k in ("하향", "↓", "낮춰", "내려", "낮춤")):
        return "하향"
    if "신규" in title:
        return "신규"
    return "유지"
