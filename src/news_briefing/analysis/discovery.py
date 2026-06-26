"""발굴 트랙 오케스트레이션 — 유니버스 로드 → 펀더멘털 수집 → 정량 스크린.

`screen` 커맨드의 본체. 이벤트 구동 morning 파이프라인과 분리된, 사용자가 명시적으로
실행하는 온디맨드 트랙이다. Phase 2 에서 LLM 심층 리서치(`deep_research`)가 숏리스트
위에 얹히고, Phase 3 에서 스냅샷 저장·앱 주입이 붙는다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from news_briefing.analysis.screener import ScreenResult, screen
from news_briefing.collectors.fundamentals import fetch_fundamentals
from news_briefing.config import PROJECT_ROOT

log = logging.getLogger(__name__)

_UNIVERSE_PATH = PROJECT_ROOT / "data" / "universe.json"

# scope 별 숏리스트 크기.
TOP_N = 20


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    us: list[ScreenResult]
    kospi: list[ScreenResult]


def load_universe(path: Path | None = None) -> dict[str, list[str]]:
    """data/universe.json 로드. 없으면 빈 유니버스."""
    p = path or _UNIVERSE_PATH
    if not p.exists():
        log.warning("유니버스 파일 없음: %s — `python scripts/build_universe.py` 실행 필요", p)
        return {"us": [], "kospi": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"us": data.get("us", []), "kospi": data.get("kospi", [])}


def run_screen(*, top_n: int = TOP_N) -> DiscoveryResult:
    """유니버스를 펀더멘털 스크린해 scope 별 숏리스트 반환(LLM 없음)."""
    universe = load_universe()

    us_funds = fetch_fundamentals(universe["us"], scope="us")
    kospi_funds = fetch_fundamentals(universe["kospi"], scope="kospi")

    us = screen(us_funds, top_n=top_n)
    kospi = screen(kospi_funds, top_n=top_n)

    log.info("발굴 스크린 완료 US %d · KOSPI %d", len(us), len(kospi))
    return DiscoveryResult(us=us, kospi=kospi)
