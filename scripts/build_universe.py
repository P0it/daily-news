"""펀더멘털 발굴 스크린용 유니버스(data/universe.json) 생성 스크립트.

발굴 트랙은 '이벤트가 발생한 종목'이 아니라 '조용히 좋은 종목'을 찾으므로,
뉴스 흐름과 무관한 **고정 유니버스**를 정량 스캔한다. 이 스크립트가 그 유니버스를
권위 있는 소스에서 한 번 생성해 커밋용 정적 파일로 떨군다(주기적 수동 갱신).

- 미국: Wikipedia 의 S&P 500 + Nasdaq-100 구성종목(자동 수집, UA 헤더 필요).
- 코스피: KRX 자동 다운로드가 막혀 있어, 검증된 대형·중형 코드 상수 리스트를 쓴다
  (yfinance 형식 .KS 접미사). 시총 상위 위주이며 필요 시 손으로 보강한다.

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
_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NDX_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

# 코스피 대형·중형 핵심(시총 상위). yfinance 심볼(.KS). 발굴은 넓을수록 좋으나
# 잘못된 코드는 스크린을 오염시키므로, 확신 있는 종목만 둔다. 갱신은 수동.
_KOSPI: list[str] = [
    "005930.KS",  # 삼성전자
    "000660.KS",  # SK하이닉스
    "373220.KS",  # LG에너지솔루션
    "207940.KS",  # 삼성바이오로직스
    "005380.KS",  # 현대차
    "000270.KS",  # 기아
    "068270.KS",  # 셀트리온
    "035420.KS",  # NAVER
    "035720.KS",  # 카카오
    "005490.KS",  # POSCO홀딩스
    "051910.KS",  # LG화학
    "006400.KS",  # 삼성SDI
    "105560.KS",  # KB금융
    "055550.KS",  # 신한지주
    "086790.KS",  # 하나금융지주
    "316140.KS",  # 우리금융지주
    "028260.KS",  # 삼성물산
    "012330.KS",  # 현대모비스
    "096770.KS",  # SK이노베이션
    "066570.KS",  # LG전자
    "015760.KS",  # 한국전력
    "032830.KS",  # 삼성생명
    "329180.KS",  # HD현대중공업
    "017670.KS",  # SK텔레콤
    "030200.KS",  # KT
    "033780.KS",  # KT&G
    "003670.KS",  # 포스코퓨처엠
    "009150.KS",  # 삼성전기
    "010130.KS",  # 고려아연
    "011200.KS",  # HMM
    "024110.KS",  # 기업은행
    "316140.KS",  # (중복 방지용; set 처리)
    "010950.KS",  # S-Oil
    "018260.KS",  # 삼성에스디에스
    "034730.KS",  # SK
    "003550.KS",  # LG
    "267260.KS",  # HD현대일렉트릭
    "042660.KS",  # 한화오션
    "009540.KS",  # HD한국조선해양
    "012450.KS",  # 한화에어로스페이스
    "047810.KS",  # 한국항공우주
    "010140.KS",  # 삼성중공업
    "064350.KS",  # 현대로템
    "086280.KS",  # 현대글로비스
    "161390.KS",  # 한국타이어앤테크놀로지
    "000810.KS",  # 삼성화재
    "138040.KS",  # 메리츠금융지주
    "316140.KS",
    "323410.KS",  # 카카오뱅크
    "377300.KS",  # 카카오페이
    "259960.KS",  # 크래프톤
    "036570.KS",  # 엔씨소프트
    "251270.KS",  # 넷마블
    "352820.KS",  # 하이브
    "090430.KS",  # 아모레퍼시픽
    "051900.KS",  # LG생활건강
    "271560.KS",  # 오리온
    "097950.KS",  # CJ제일제당
    "139480.KS",  # 이마트
    "069960.KS",  # 현대백화점
    "004020.KS",  # 현대제철
    "001040.KS",  # CJ
    "302440.KS",  # SK바이오사이언스
    "128940.KS",  # 한미약품
    "000100.KS",  # 유한양행
    "326030.KS",  # SK바이오팜
    "011170.KS",  # 롯데케미칼
    "009830.KS",  # 한화솔루션
    "047050.KS",  # 포스코인터내셔널
    "010120.KS",  # LS일렉트릭
    "006260.KS",  # LS
    "267250.KS",  # HD현대
    "375500.KS",  # DL이앤씨
    "000720.KS",  # 현대건설
    "028050.KS",  # 삼성엔지니어링
    "088350.KS",  # 한화생명
    "071050.KS",  # 한국금융지주
    "029780.KS",  # 삼성카드
    "180640.KS",  # 한진칼
    "003490.KS",  # 대한항공
    "180460.KS",  # (필요시 보강)
    "402340.KS",  # SK스퀘어
    "011070.KS",  # LG이노텍
    "108320.KS",  # LX세미콘
    "000990.KS",  # DB하이텍
]


def _fetch_table(url: str) -> list[pd.DataFrame]:
    resp = requests.get(url, headers=_UA, timeout=20)
    resp.raise_for_status()
    return pd.read_html(io.StringIO(resp.text))


def _norm_us(symbol: str) -> str:
    """야후 파이낸스 형식으로 정규화 (BRK.B → BRK-B)."""
    return symbol.strip().upper().replace(".", "-")


def fetch_us() -> list[str]:
    """S&P 500 + Nasdaq-100 구성종목 심볼을 합쳐 중복 제거."""
    tickers: set[str] = set()

    sp = _fetch_table(_SP500_URL)[0]
    for s in sp["Symbol"].tolist():
        tickers.add(_norm_us(str(s)))

    for tbl in _fetch_table(_NDX_URL):
        cols = [str(c) for c in tbl.columns]
        if any(c in ("Ticker", "Symbol") for c in cols):
            col = "Ticker" if "Ticker" in cols else "Symbol"
            for s in tbl[col].tolist():
                tickers.add(_norm_us(str(s)))
            break

    return sorted(tickers)


def build() -> dict[str, list[str]]:
    us = fetch_us()
    kospi = sorted(set(_KOSPI))
    return {"us": us, "kospi": kospi}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="발굴 스크린 유니버스 생성")
    parser.add_argument(
        "--print", action="store_true", dest="print_only", help="파일에 쓰지 않고 요약만 출력"
    )
    args = parser.parse_args(argv)

    universe = build()
    summary = f"US {len(universe['us'])}종목 · KOSPI {len(universe['kospi'])}종목"

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
