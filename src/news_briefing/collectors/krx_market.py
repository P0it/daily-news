"""KRX 공식 Open API 일별매매정보 수집기.

`data.krx.co.kr` 의 내부 JSON 엔드포인트는 세션 인증을 요구하고(`400 LOGOUT`),
`pykrx` 도 최신 버전이 KRX 로그인을 요구해 쓸 수 없다(DECISIONS #20). 대신
2026년 기준 공개된 **KRX Open API**(`openapi.krx.co.kr` 에서 AUTH_KEY 발급)를
쓴다. 무료 신청이며 헤더 `AUTH_KEY` 하나로 인증한다.

제공 범위는 전종목 일별 시세·거래량·거래대금·시가총액까지다. 투자자별 순매수나
공매도 잔고는 이 API 에 없으므로 여기서 다루지 않는다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

KRX_API_BASE = "https://data-dbg.krx.co.kr/svc/apis/sto"

# (엔드포인트, 시장 표기) — 코넥스(knx_bydd_trd)는 유동성이 없어 제외
_MARKETS: list[tuple[str, str]] = [
    ("stk_bydd_trd", "KOSPI"),
    ("ksq_bydd_trd", "KOSDAQ"),
]


@dataclass(frozen=True, slots=True)
class KrxDaily:
    """전종목 일별매매정보 한 종목분."""

    bas_dd: str  # 기준일 YYYYMMDD
    code: str  # 단축코드 6자리
    name: str
    market: str  # KOSPI | KOSDAQ
    sector: str  # 소속부/업종 (없으면 "")
    close: float  # 종가 (원)
    change: float  # 전일대비 (원)
    change_pct: float  # 등락률 (%)
    volume: int  # 누적 거래량 (주)
    value: int  # 누적 거래대금 (원)
    market_cap: int  # 시가총액 (원)


def _pick(row: dict, *keys: str) -> str:
    """응답 필드명이 버전에 따라 흔들려도 견디도록 후보 키를 순서대로 조회한다."""
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return str(v)
    return ""


def _num(raw: str) -> float:
    """'1,234' · '-' · '' 같은 KRX 표기를 float 로. 파싱 불가 시 0.0."""
    s = raw.replace(",", "").strip()
    if not s or s in ("-", "null"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_krx_rows(data: dict, market: str) -> list[KrxDaily]:
    """Open API 응답(OutBlock_1)을 KrxDaily 리스트로 변환한다."""
    rows = data.get("OutBlock_1") or data.get("outBlock_1") or []
    items: list[KrxDaily] = []
    for row in rows:
        code = _pick(row, "ISU_SRT_CD", "ISU_CD")
        # 우선주·리츠 등 비표준 코드는 6자리 숫자 필터로 걸러진다
        if not code.isdigit() or len(code) != 6:
            continue
        items.append(
            KrxDaily(
                bas_dd=_pick(row, "BAS_DD"),
                code=code,
                name=_pick(row, "ISU_NM", "ISU_ABBRV"),
                market=_pick(row, "MKT_NM") or market,
                sector=_pick(row, "SECT_TP_NM", "IDX_IND_NM"),
                close=_num(_pick(row, "TDD_CLSPRC")),
                change=_num(_pick(row, "CMPPREVDD_PRC")),
                change_pct=_num(_pick(row, "FLUC_RT")),
                volume=int(_num(_pick(row, "ACC_TRDVOL"))),
                value=int(_num(_pick(row, "ACC_TRDVAL"))),
                market_cap=int(_num(_pick(row, "MKTCAP"))),
            )
        )
    return items


def fetch_krx_daily(
    auth_key: str,
    bas_dd: str,  # YYYYMMDD
    *,
    timeout: int = 20,
) -> list[KrxDaily]:
    """지정일의 코스피+코스닥 전종목 일별매매정보를 반환한다.

    휴장일이면 빈 리스트가 온다(에러 아님). 키가 없거나 인증 실패면 경고만 남기고
    빈 리스트 — 수집기 하나가 죽어도 파이프라인은 계속 간다는 원칙을 따른다.
    """
    if not auth_key:
        log.warning("KRX_API_KEY 없음, KRX 수집 스킵")
        return []

    items: list[KrxDaily] = []
    for endpoint, market in _MARKETS:
        try:
            resp = requests.get(
                f"{KRX_API_BASE}/{endpoint}",
                params={"basDd": bas_dd},
                headers={"AUTH_KEY": auth_key},
                timeout=timeout,
            )
            if resp.status_code == 401:
                log.error("KRX 인증 실패(401) — AUTH_KEY 확인 필요")
                return []
            resp.raise_for_status()
            items.extend(parse_krx_rows(resp.json(), market))
        except Exception as e:
            log.error("KRX 수집 실패 endpoint=%s bas_dd=%s: %s", endpoint, bas_dd, e)
    return items


def fetch_recent_trading_days(
    auth_key: str,
    *,
    asof: date | None = None,
    days: int = 6,
    max_lookback: int = 20,
) -> list[list[KrxDaily]]:
    """최근 거래일 `days` 개를 최신순으로 반환한다.

    KRX 는 휴장일에 빈 응답을 주므로 달력 대신 응답 유무로 거래일을 판별하고,
    무한 루프를 막기 위해 `max_lookback` 일까지만 거슬러 올라간다.
    """
    cur = asof or date.today()
    out: list[list[KrxDaily]] = []
    for _ in range(max_lookback):
        if len(out) >= days:
            break
        rows = fetch_krx_daily(auth_key, cur.strftime("%Y%m%d"))
        if rows:
            out.append(rows)
        else:
            log.debug("KRX %s 데이터 없음(휴장 추정)", cur)
        cur -= timedelta(days=1)
    if len(out) < days:
        log.warning("KRX 거래일 %d개 요청했으나 %d개만 확보", days, len(out))
    return out
