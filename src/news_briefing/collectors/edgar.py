"""SEC EDGAR 8-K + Form 4 Atom 수집기.

User-Agent 필수 (SEC policy).
https://www.sec.gov/os/accessing-edgar-data
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from news_briefing.collectors.base import CollectedItem

log = logging.getLogger(__name__)

EDGAR_BROWSE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}

# 제목 패턴: "4 - COMPANY NAME (0001234567) (Issuer)" 또는 "8-K - APPLE INC (0000320193)"
TITLE_RE = re.compile(r"^(?:[^-]+)-\s*(.+?)\s*\((\d+)\)")
ITEM_RE = re.compile(r"Item\s*(\d+\.\d+)", re.IGNORECASE)


def parse_edgar_atom(content: str, form_type: str) -> list[CollectedItem]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        log.error("EDGAR atom parse 실패: %s", e)
        return []

    items: list[CollectedItem] = []
    for entry in root.findall("a:entry", ATOM_NS):
        title_el = entry.find("a:title", ATOM_NS)
        link_el = entry.find("a:link", ATOM_NS)
        id_el = entry.find("a:id", ATOM_NS)
        updated_el = entry.find("a:updated", ATOM_NS)
        summary_el = entry.find("a:summary", ATOM_NS)

        if title_el is None or link_el is None or id_el is None:
            continue

        title = (title_el.text or "").strip()
        m = TITLE_RE.match(title)
        company = m.group(1).strip() if m else title
        cik = m.group(2) if m else ""

        url = link_el.get("href", "")
        ext_id = (id_el.text or "").strip() or url

        published = datetime.now()
        if updated_el is not None and updated_el.text:
            try:
                # 원본은 timezone-aware. 로컬 naive 로 변환해 다른 CollectedItem 과 맞춤
                parsed = datetime.fromisoformat(updated_el.text.replace("Z", "+00:00"))
                published = parsed.replace(tzinfo=None)
            except Exception:
                pass

        summary_text = (summary_el.text or "") if summary_el is not None else ""
        item_match = ITEM_RE.search(summary_text)
        items_str = item_match.group(1) if item_match else ""

        items.append(
            CollectedItem(
                source="edgar",
                ext_id=ext_id,
                kind="disclosure",
                title=f"{form_type} — {company}",
                url=url,
                published_at=published,
                company=company,
                company_code=cik,
                extra={
                    "form_type": form_type,
                    "cik": cik,
                    "items": items_str,
                },
            )
        )
    return items


def _fetch_atom(
    form_type: str, *, user_agent: str, count: int = 40, timeout: int = 15
) -> list[CollectedItem]:
    if not user_agent:
        log.warning("EDGAR User-Agent 없음, 수집 스킵 (.env 의 EDGAR_USER_AGENT)")
        return []
    try:
        resp = requests.get(
            EDGAR_BROWSE_URL,
            params={
                "action": "getcompany",
                "type": form_type,
                "dateb": "",
                "owner": "include",
                "count": count,
                "output": "atom",
            },
            headers={
                "User-Agent": user_agent,
                "Accept": "application/atom+xml",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return parse_edgar_atom(resp.text, form_type)
    except Exception as e:
        log.error("EDGAR %s 수집 실패: %s", form_type, e)
        return []


def fetch_edgar_form4(*, user_agent: str, count: int = 40) -> list[CollectedItem]:
    return _fetch_atom("4", user_agent=user_agent, count=count)


def fetch_edgar_8k(*, user_agent: str, count: int = 40) -> list[CollectedItem]:
    return _fetch_atom("8-K", user_agent=user_agent, count=count)


def fetch_all_edgar(user_agent: str) -> list[CollectedItem]:
    """EDGAR Form 4 + 8-K 동시 수집 (한 쪽 실패해도 다른 쪽 진행)."""
    return fetch_edgar_form4(user_agent=user_agent) + fetch_edgar_8k(
        user_agent=user_agent
    )
