"""내부자 집단 매수 탐지기 (SEC Form 4 클러스터 분석).

단건 내부자 거래(노이즈)가 아닌 동일 회사에 90일 내 3인 이상 매수 집중 패턴을 감지.
집단 매수는 단순 뉴스보다 앞서 기관/내부 정보 우위 가능성을 시사하는 선행 지표.

의존: 기존 edgar.py Form 4 아이템이 DB에 누적되어 있어야 함.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

_EDGAR_ATOM_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcompany&type=4&dateb=&owner=include&count=200&search_text="
    "&action=getcompany"
)
_TIMEOUT = 15

# 집단 매수 기준
CLUSTER_MIN_INSIDERS = 3   # 동일 회사에 몇 명 이상 매수해야 클러스터로 인정
CLUSTER_WINDOW_DAYS = 90   # 집계 기간


def _parse_form4_feed(content: str, user_agent: str) -> list[dict]:
    """EDGAR Form 4 Atom 피드 → 내부자 거래 레코드 목록."""
    import xml.etree.ElementTree as ET
    import re

    ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
    TITLE_RE = re.compile(r"^(?:[^-]+)-\s*(.+?)\s*\((\d+)\)")

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        log.error("Form4 atom parse 실패: %s", e)
        return []

    records = []
    for entry in root.findall("a:entry", ATOM_NS):
        title_el = entry.find("a:title", ATOM_NS)
        id_el = entry.find("a:id", ATOM_NS)
        updated_el = entry.find("a:updated", ATOM_NS)
        summary_el = entry.find("a:summary", ATOM_NS)

        if title_el is None or id_el is None:
            continue

        title = (title_el.text or "").strip()
        m = TITLE_RE.match(title)
        company = m.group(1).strip() if m else title
        cik = m.group(2) if m else ""

        updated_str = (updated_el.text or "").strip() if updated_el is not None else ""
        try:
            filed_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        except ValueError:
            filed_at = datetime.now(timezone.utc)

        summary_text = (summary_el.text or "").lower() if summary_el is not None else ""
        # 매수 여부 — 요약에 'purchase', 'acquired' 포함, 'sale'/'disposed' 없을 때
        is_buy = (
            ("purchase" in summary_text or "acquired" in summary_text or "acquisition" in summary_text)
            and "sale" not in summary_text
            and "disposed" not in summary_text
        )
        records.append({
            "company": company,
            "cik": cik,
            "filed_at": filed_at,
            "is_buy": is_buy,
            "title": title,
            "ext_id": (id_el.text or "").strip(),
        })
    return records


def fetch_insider_clusters(
    user_agent: str,
    lookback_days: int = CLUSTER_WINDOW_DAYS,
    min_insiders: int = CLUSTER_MIN_INSIDERS,
) -> list[CollectedItem]:
    """최근 lookback_days 내 집단 매수 클러스터 탐지 → CollectedItem 리스트 반환.

    단일 Form 4가 아닌 동일 CIK에 여러 내부자가 매수한 패턴만 반환.
    """
    try:
        resp = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar"
            "?action=getcompany&type=4&dateb=&owner=include&count=200&output=atom",
            headers={"User-Agent": user_agent},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        records = _parse_form4_feed(resp.text, user_agent)
    except Exception as e:
        log.error("Form 4 피드 조회 실패: %s", e)
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=lookback_days)

    # CIK별 매수 기록 집계
    cik_buys: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        if rec["is_buy"] and rec["filed_at"] >= cutoff:
            cik_buys[rec["cik"]].append(rec)

    items: list[CollectedItem] = []
    for cik, buys in cik_buys.items():
        if len(buys) < min_insiders:
            continue

        company = buys[0]["company"]
        latest = max(buys, key=lambda r: r["filed_at"])
        count = len(buys)

        # 클러스터 규모별 점수
        if count >= 6:
            score = 92
        elif count >= 4:
            score = 85
        else:
            score = 78

        headline = (
            f"[내부자 집단매수] {company} — {count}명 {lookback_days}일 내 집중 매수 감지"
        )
        summary = (
            f"최근 {lookback_days}일 동안 {company} 내부자 {count}명이 자사주를 매수했습니다. "
            "집단 매수는 개별 거래보다 강한 신뢰 신호로 해석돼요."
        )

        items.append(
            CollectedItem(
                source="edgar_cluster",
                ext_id=f"cluster_{cik}_{now.strftime('%Y%m%d')}",
                kind="disclosure",
                title=headline,
                url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4",
                published_at=latest["filed_at"],
                body=summary,
                company=company,
                company_code=cik,
                extra={
                    "scope": "foreign",
                    "cluster_count": count,
                    "cluster_window_days": lookback_days,
                    "cik": cik,
                    "pre_scored": score,
                },
            )
        )

    log.info("insider_cluster: %d개 클러스터 탐지 (기준 %d인 이상)", len(items), min_insiders)
    return items
