"""펀더멘털 발굴 스크린용 유니버스(data/universe.json) 생성 스크립트.

발굴 트랙은 '이벤트가 발생한 종목'이 아니라 '조용히 좋은 종목'을 찾으므로,
뉴스 흐름과 무관한 **고정 유니버스**를 정량 스캔한다. 이 스크립트가 그 유니버스를
권위 있는 소스에서 한 번 생성해 커밋용 정적 파일로 떨군다(주기적 수동 갱신).

- 미국: NASDAQ Trader 심볼 디렉토리(nasdaqlisted + otherlisted) — 나스닥·NYSE·
  AMEX 전 상장 보통주. ETF·테스트종목·워런트·권리·SPAC 등은 제외. 예전엔
  S&P500+Nasdaq100(대형주 지수)만 썼는데, 그러면 이미 다 아는 대형주만 스크린되어
  '발굴'이 안 됐다 — 지수 밖 중소형주까지 담으려 전체 디렉토리로 교체했다.
- 코스피·코스닥: KRX 공식 사이트(data.krx.co.kr) 자동 다운로드는 막혀 있지만, KIND
  상장회사 목록 다운로드(kind.krx.co.kr)는 열려 있어 그걸 쓴다. 두 시장 전체를 담아
  대형주 85종목 하드코딩 상수 리스트를 대체한다.

사용:
    python scripts/build_universe.py            # data/universe.json 생성
    python scripts/build_universe.py --print    # 생성만 미리보기(파일 안 씀)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pandas as pd
import requests

_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "data" / "universe.json"

_UA = {"User-Agent": "Mozilla/5.0 (news-briefing universe builder)"}

# NASDAQ Trader 심볼 디렉토리. 공식·무료·비로그인. 매일 갱신되는 전 상장종목 목록.
_NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
_OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"

# KIND(한국거래소 상장회사 목록 다운로드). data.krx.co.kr 과 달리 UA 헤더만으로 열람 가능.
_KIND_URL = (
    "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType={market_type}"
)
_KRX_MARKETS = [("stockMkt", "KS"), ("kosdaqMkt", "KQ")]  # (KIND market_type, yfinance 접미사)

# 보통주가 아닌 종목(워런트·권리·SPAC·우선주 등)을 이름으로 걸러낸다. 대소문자 무시.
_US_EXCLUDE_NAME_KEYWORDS = (
    "warrant",
    "right",
    " unit",
    "units",
    "preferred",
    "acquisition corp",
    "acquisition corporation",
    "trust preferred",
)


def _norm_us(symbol: str) -> str:
    """야후 파이낸스 형식으로 정규화 (BRK.B → BRK-B)."""
    return symbol.strip().upper().replace(".", "-")


def _is_excluded_us_name(name: str) -> bool:
    lowered = name.lower()
    return any(kw in lowered for kw in _US_EXCLUDE_NAME_KEYWORDS)


def _fetch_symdir(url: str) -> pd.DataFrame:
    resp = requests.get(url, headers=_UA, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), sep="|")
    return df.iloc[:-1]  # 마지막 행은 "File Creation Time" 푸터


def fetch_us() -> list[str]:
    """나스닥·NYSE·AMEX 전 상장 보통주 심볼(테스트·ETF·워런트·SPAC 등 제외)."""
    tickers: set[str] = set()

    nasdaq = _fetch_symdir(_NASDAQ_LISTED_URL)
    for _, row in nasdaq.iterrows():
        if str(row.get("Test Issue")) != "N" or str(row.get("ETF")) != "N":
            continue
        # Financial Status: N=정상. 결측 부실·상장폐지 절차중 종목 제외.
        if str(row.get("Financial Status")) not in ("N", "nan"):
            continue
        if _is_excluded_us_name(str(row.get("Security Name", ""))):
            continue
        tickers.add(_norm_us(str(row["Symbol"])))

    other = _fetch_symdir(_OTHER_LISTED_URL)
    for _, row in other.iterrows():
        if str(row.get("Test Issue")) != "N" or str(row.get("ETF")) != "N":
            continue
        if _is_excluded_us_name(str(row.get("Security Name", ""))):
            continue
        symbol = row.get("NASDAQ Symbol") or row.get("ACT Symbol")
        tickers.add(_norm_us(str(symbol)))

    return sorted(tickers)


def _fetch_kind(market_type: str) -> pd.DataFrame:
    resp = requests.get(_KIND_URL.format(market_type=market_type), headers=_UA, timeout=20)
    resp.raise_for_status()
    return pd.read_html(io.BytesIO(resp.content), encoding="euc-kr")[0]


def fetch_kospi() -> list[str]:
    """코스피+코스닥 전 상장종목 → yfinance 심볼(.KS/.KQ). 우선주 등 비표준 코드 제외."""
    tickers: set[str] = set()
    for market_type, suffix in _KRX_MARKETS:
        df = _fetch_kind(market_type)
        for code in df["종목코드"]:
            code = str(code).strip()
            if len(code) == 6 and code.isdigit():
                tickers.add(f"{code}.{suffix}")
    return sorted(tickers)


def build() -> dict[str, list[str]]:
    return {"us": fetch_us(), "kospi": fetch_kospi()}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="발굴 스크린 유니버스 생성")
    parser.add_argument(
        "--print", action="store_true", dest="print_only", help="파일에 쓰지 않고 요약만 출력"
    )
    args = parser.parse_args(argv)

    universe = build()
    summary = f"US {len(universe['us'])}종목 · KOSPI(+KOSDAQ) {len(universe['kospi'])}종목"

    if args.print_only:
        print(summary)
        print("US 샘플:", universe["us"][:10])
        print("KOSPI 샘플:", universe["kospi"][:10])
        return 0

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(universe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"생성: {_OUT}  ({summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
