"""KRX 일별매매정보 로컬 파일 캐시.

과거 거래일 데이터는 확정되면 절대 바뀌지 않으므로 날짜별 JSON 으로 영구
캐시한다. 전종목 응답이 요청당 26~30초 걸리는 KRX Open API 의 반복 호출을
없애 급상승 조회·아침 배치를 크게 단축한다. 당일치는 장중 미확정이라 캐시하지
않고, 빈 결과(휴장·에러)도 캐시하지 않아 일시적 서버 오류가 캐시를 오염시키지
않게 한다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date
from pathlib import Path

from news_briefing.collectors.krx_market import KrxDaily

log = logging.getLogger(__name__)

_CACHE_DIR = Path("data/krx_cache")


def _cache_path(bas_dd: str) -> Path:
    return _CACHE_DIR / f"{bas_dd}.json"


def load_cached_day(bas_dd: str) -> list[KrxDaily] | None:
    """캐시된 하루치를 반환한다. 없거나 읽기 실패면 None."""
    p = _cache_path(bas_dd)
    if not p.exists():
        return None
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
        return [KrxDaily(**r) for r in rows]
    except Exception as e:  # 캐시 손상은 치명적이지 않다 — 재수집으로 폴백
        log.warning("KRX 캐시 읽기 실패 %s: %s", p, e)
        return None


def save_cached_day(bas_dd: str, items: list[KrxDaily]) -> None:
    """하루치를 캐시에 저장한다. 빈 결과·당일치는 저장하지 않는다."""
    if not items:
        return
    if bas_dd == date.today().strftime("%Y%m%d"):
        return  # 장중 미확정 데이터가 굳어버리는 것을 막는다
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(bas_dd).write_text(
            json.dumps([asdict(it) for it in items], ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning("KRX 캐시 저장 실패 %s: %s", bas_dd, e)
