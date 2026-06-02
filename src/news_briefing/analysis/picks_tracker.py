"""추천 종목 성과 추적기.

hotIssues.picks에서 추천 종목을 추출하고, yfinance로 추천 시점 종가와
현재 종가를 조회해 frontend/public/picks_history.json에 저장한다.

CLI: python -m news_briefing.analysis.picks_tracker
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yfinance as yf

log = logging.getLogger(__name__)

# ── 경로 ────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]
PICKS_HISTORY_PATH = _REPO_ROOT / "frontend" / "public" / "picks_history.json"

# 최대 추적 기간 (이 기간 이전 picks는 성과 갱신 중단)
MAX_TRACK_DAYS = 30


@dataclass
class PickRecord:
    id: str  # "{date}-{ticker}"
    date: str  # "YYYY-MM-DD"
    ticker: str
    name: str
    scope: str  # "domestic" | "foreign"
    direction: str  # "positive" | "negative" | ...
    theme: str  # hotIssue asset 이름
    rationale: str  # pick description
    price_at_rec: float | None  # 추천일 종가
    currency: str  # "KRW" | "USD" | ...
    current_price: float | None
    current_price_at: str | None  # ISO8601
    change_pct: float | None


# ── picks 추출 ──────────────────────────────────────────────────────────────


def extract_picks(briefing: dict[str, Any]) -> list[PickRecord]:
    """브리핑 dict에서 hotIssues picks를 PickRecord 리스트로 변환."""
    date_str: str = briefing.get("date", "")
    records: list[PickRecord] = []

    economy = briefing.get("tabs", {}).get("economy", {})
    hot_issues = economy.get("hotIssues", {})

    for scope in ("domestic", "foreign"):
        for issue in hot_issues.get(scope, []):
            theme = issue.get("asset", "")
            direction = issue.get("direction", "positive")
            picks = issue.get("picks") or []
            for pick in picks:
                ticker = pick.get("ticker", "").strip()
                if not ticker:
                    continue
                rec_id = f"{date_str}-{ticker}"
                currency = "USD" if scope == "foreign" else "KRW"
                records.append(
                    PickRecord(
                        id=rec_id,
                        date=date_str,
                        ticker=ticker,
                        name=pick.get("name", ticker),
                        scope=scope,
                        direction=direction,
                        theme=theme,
                        rationale=pick.get("description", ""),
                        price_at_rec=None,
                        currency=currency,
                        current_price=None,
                        current_price_at=None,
                        change_pct=None,
                    )
                )
    return records


# ── 가격 조회 ────────────────────────────────────────────────────────────────


def _yf_ticker(ticker: str, scope: str) -> list[str]:
    """yfinance에 시도할 ticker 후보 목록 반환."""
    if scope == "foreign":
        return [ticker]
    # 국내 종목: KRX 상장은 .KS(KOSPI) 또는 .KQ(KOSDAQ)
    return [f"{ticker}.KS", f"{ticker}.KQ"]


def fetch_price(ticker: str, scope: str, date_str: str) -> float | None:
    """지정 날짜 종가를 반환. 조회 실패 시 None."""
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
        # yfinance는 end를 exclusive로 받으므로 다음 날까지 범위로 조회
        start = target.strftime("%Y-%m-%d")
        end = (target + timedelta(days=4)).strftime("%Y-%m-%d")  # 휴장 대비 여유

        candidates = _yf_ticker(ticker, scope)
        for yt in candidates:
            try:
                df = yf.download(yt, start=start, end=end, progress=False, auto_adjust=True)
                if df.empty:
                    continue
                # yfinance는 멀티인덱스 컬럼 반환 — ("Close", ticker) 또는 단순 "Close"
                if hasattr(df.columns, "levels"):
                    # MultiIndex: ("Close", "005930.KS") 형태
                    close_vals = df["Close"]
                    if hasattr(close_vals, "iloc"):
                        val = close_vals.iloc[0]
                        if hasattr(val, "iloc"):
                            val = float(val.iloc[0])
                        else:
                            val = float(val)
                    else:
                        continue
                else:
                    if "Close" not in df.columns:
                        continue
                    val = float(df["Close"].iloc[0])
                price = val
                log.debug("price %s on %s: %.4f", yt, date_str, price)
                return price
            except Exception:
                continue
    except Exception as e:
        log.warning("fetch_price 실패 (%s, %s): %s", ticker, date_str, e)
    return None


def fetch_current_price(ticker: str, scope: str) -> tuple[float | None, str | None]:
    """현재 종가와 조회 시각(ISO8601) 반환."""
    today = datetime.now(tz=UTC)
    price = fetch_price(ticker, scope, today.strftime("%Y-%m-%d"))
    # 오늘 데이터가 없으면 어제
    if price is None:
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        price = fetch_price(ticker, scope, yesterday)
    if price is None:
        return None, None
    return price, today.isoformat()


# ── 히스토리 갱신 ────────────────────────────────────────────────────────────


def _load_history(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("picks_history.json 파싱 실패, 초기화: %s", e)
    return {"updatedAt": "", "records": []}


def _save_history(path: Path, records: list[PickRecord]) -> None:
    now = datetime.now(tz=UTC).isoformat()
    data = {
        "updatedAt": now,
        "records": [_to_json(r) for r in records],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("picks_history.json 저장: %d건", len(records))


def _to_json(r: PickRecord) -> dict[str, Any]:
    d = asdict(r)
    # camelCase로 변환
    return {
        "id": d["id"],
        "date": d["date"],
        "ticker": d["ticker"],
        "name": d["name"],
        "scope": d["scope"],
        "direction": d["direction"],
        "theme": d["theme"],
        "rationale": d["rationale"],
        "priceAtRec": d["price_at_rec"],
        "currency": d["currency"],
        "currentPrice": d["current_price"],
        "currentPriceAt": d["current_price_at"],
        "changePct": d["change_pct"],
    }


def _from_json(d: dict[str, Any]) -> PickRecord:
    return PickRecord(
        id=d["id"],
        date=d["date"],
        ticker=d["ticker"],
        name=d["name"],
        scope=d["scope"],
        direction=d["direction"],
        theme=d["theme"],
        rationale=d["rationale"],
        price_at_rec=d.get("priceAtRec"),
        currency=d.get("currency", "USD"),
        current_price=d.get("currentPrice"),
        current_price_at=d.get("currentPriceAt"),
        change_pct=d.get("changePct"),
    )


def _calc_change_pct(price_at_rec: float | None, current: float | None) -> float | None:
    if price_at_rec and current and price_at_rec > 0:
        return round((current - price_at_rec) / price_at_rec * 100, 2)
    return None


def update_history(
    briefings: list[dict[str, Any]],
    history_path: Path = PICKS_HISTORY_PATH,
) -> None:
    """브리핑 목록에서 picks를 추출하고 가격을 갱신해 파일에 저장.

    Args:
        briefings: date 기준 내림차순 브리핑 dict 목록
        history_path: 저장할 JSON 경로
    """
    existing = _load_history(history_path)
    records_by_id: dict[str, PickRecord] = {
        r["id"]: _from_json(r) for r in existing.get("records", [])
    }

    cutoff = datetime.now(tz=UTC) - timedelta(days=MAX_TRACK_DAYS)
    cutoff_date = cutoff.strftime("%Y-%m-%d")

    # 브리핑에 포함된 날짜는 기존 records를 완전히 교체 (재실행 시 중복 방지)
    briefing_dates = {
        b.get("date", "")
        for b in briefings
        if b.get("date", "") >= cutoff_date
    }
    records_by_id = {
        rid: rec
        for rid, rec in records_by_id.items()
        if rec.date not in briefing_dates
    }

    # 최신 브리핑 picks 추가
    new_count = 0
    for briefing in briefings:
        date_str = briefing.get("date", "")
        if date_str < cutoff_date:
            continue
        for rec in extract_picks(briefing):
            records_by_id[rec.id] = rec
            new_count += 1

    log.info("picks 갱신: %d건 (날짜 교체: %s)", new_count, sorted(briefing_dates))

    # 전체 picks 가격 갱신
    all_records = list(records_by_id.values())
    # 오래된 records는 currentPrice만 갱신하고 change_pct 재계산
    for i, rec in enumerate(all_records):
        if rec.date < cutoff_date:
            continue
        try:
            # 추천일 종가가 없으면 조회
            if rec.price_at_rec is None:
                rec.price_at_rec = fetch_price(rec.ticker, rec.scope, rec.date)

            # 현재가 갱신
            cur_price, cur_at = fetch_current_price(rec.ticker, rec.scope)
            rec.current_price = cur_price
            rec.current_price_at = cur_at
            rec.change_pct = _calc_change_pct(rec.price_at_rec, rec.current_price)
            all_records[i] = rec
        except Exception as e:
            log.warning("가격 갱신 실패 (%s): %s", rec.id, e)

    # 최신 순 정렬 후 저장
    all_records.sort(key=lambda r: r.date, reverse=True)
    _save_history(history_path, all_records)


# ── Supabase에서 브리핑 로드 ────────────────────────────────────────────────


def load_briefings_from_supabase(limit: int = 30) -> list[dict[str, Any]]:
    """Supabase briefings 테이블에서 최근 N개 브리핑을 로드."""
    from news_briefing.config import load_config  # noqa: PLC0415
    from news_briefing.storage.db import get_client  # noqa: PLC0415

    cfg = load_config()
    conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
    resp = (
        conn.table("briefings").select("date, data").order("date", desc=True).limit(limit).execute()
    )
    briefings = []
    for row in resp.data or []:
        data = row.get("data")
        if isinstance(data, dict):
            briefings.append(data)
    return briefings


def load_briefings_from_local(briefings_dir: Path | None = None) -> list[dict[str, Any]]:
    """로컬 frontend/public/briefings/ 디렉토리에서 브리핑 JSON 로드."""
    if briefings_dir is None:
        briefings_dir = _REPO_ROOT / "frontend" / "public" / "briefings"
    files = sorted(briefings_dir.glob("????-??-??.json"), reverse=True)[:MAX_TRACK_DAYS]
    briefings = []
    for f in files:
        try:
            briefings.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            log.warning("브리핑 파일 로드 실패 (%s): %s", f.name, e)
    return briefings


# ── CLI 진입점 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    # Supabase 시도, 실패하면 로컬 파일 사용
    briefings: list[dict[str, Any]] = []
    try:
        briefings = load_briefings_from_supabase()
        log.info("Supabase에서 %d개 브리핑 로드", len(briefings))
    except Exception as e:
        log.warning("Supabase 로드 실패, 로컬 파일 사용: %s", e)

    if not briefings:
        briefings = load_briefings_from_local()
        log.info("로컬에서 %d개 브리핑 로드", len(briefings))

    if not briefings:
        log.error("브리핑 데이터 없음. 종료.")
        import sys

        sys.exit(1)

    update_history(briefings, PICKS_HISTORY_PATH)
    print(f"picks_history.json 생성 완료: {PICKS_HISTORY_PATH}")
