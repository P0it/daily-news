"""발굴 픽 영구 원장 + T+5/20/60 거래일 알파 채점.

pick_outcomes(촉매 픽)의 자매. 발굴 픽도 추천 시점가 대비 **지수 초과수익(alpha)**으로
채점한다 — "진짜 발굴이면 시장과 무관하게 알파를 낸다"(메모리: 픽 평가 철학). 발굴은
중장기 아이디어라 호라이즌이 더 길다(5/20/60 거래일).

촉매 픽과 달리 direction 은 항상 positive(롱 아이디어)다. 점수·벤치 계산 헬퍼는
picks_outcomes 에서 재사용하고, 다운로드만 자체 구현한다(발굴 티커는 .KS 포함 완전한
yfinance 심볼이라 picks 의 _yf_ticker 후보 확장이 맞지 않음).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import yfinance as yf

from news_briefing.analysis.picks_outcomes import (
    BENCH_SYMBOL,
    _bench_baseline,
    _bench_on,
    _bench_series,
    _series_dict,
    score_horizon,
)
from news_briefing.storage import discovery_outcomes as store
from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)

# 발굴은 중장기 — 5/20/60 거래일에 채점.
DHORIZONS: list[tuple[str, int]] = [("5d", 4), ("20d", 19), ("60d", 59)]

# 60 거래일(~84일) + 여유. 이보다 오래된 미채점 픽은 백필 재시도 중단.
MAX_BACKFILL_DAYS = 120

# scope → 벤치마크 키(picks_outcomes.BENCH_SYMBOL).
_BENCH_KEY = {"us": "FOREIGN", "kospi": "KOSPI"}

_DIRECTION = "positive"  # 발굴 픽은 전부 롱 아이디어


def _download(ticker: str, start: str) -> Any:
    """ticker(완전한 yfinance 심볼)의 start~오늘 일별 종가 df. 실패 시 None."""
    today = datetime.now(tz=UTC).date()
    end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    except Exception:
        return None
    return df if (df is not None and not df.empty) else None


# ── 원장 스냅샷 (스크린 실행 시점) ────────────────────────────────────────────


def _snapshot_rows(snapshot: dict, rec_date: str) -> list[dict[str, Any]]:
    """발굴 스냅샷({us[], kospi[]}) → 원장 행(채점 시점 null)."""
    now = datetime.now(tz=UTC).isoformat()
    rows: list[dict[str, Any]] = []
    for scope in ("us", "kospi"):
        for it in snapshot.get(scope, []):
            ticker = (it.get("ticker") or "").strip()
            if not ticker:
                continue
            rows.append(
                {
                    "id": f"{rec_date}-{scope}-{ticker}",
                    "rec_date": rec_date,
                    "ticker": ticker,
                    "name": it.get("name"),
                    "scope": scope,
                    "sector": it.get("sector"),
                    "composite": it.get("composite"),
                    "value_score": it.get("valueScore"),
                    "quality_score": it.get("qualityScore"),
                    "growth_score": it.get("growthScore"),
                    "highlights": ",".join(it.get("highlights") or []),
                    "currency": "USD" if scope == "us" else "KRW",
                    "price_at_rec": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
    return rows


def record_outcomes(conn: Connection, snapshot: dict, rec_date: str) -> int:
    """스크린 스냅샷의 신규 픽을 원장에 스냅샷한다. 기록한 신규 행 수 반환.

    이미 있는 id(같은 날 재실행)는 건드리지 않는다. 진입 기준가는 백필 때 자기일관으로
    채우므로 여기서는 None 으로 두고 행만 생성한다.
    """
    rows = _snapshot_rows(snapshot, rec_date)
    if not rows:
        return 0
    existing = store.fetch_existing_ids(conn, [r["id"] for r in rows])
    new_rows = [r for r in rows if r["id"] not in existing]
    if not new_rows:
        return 0
    store.upsert_outcomes(conn, new_rows)
    log.info("discovery_outcomes 스냅샷: 신규 %d건", len(new_rows))
    return len(new_rows)


# ── 채점 백필 (T+N 종가) ─────────────────────────────────────────────────────


def backfill_outcomes(conn: Connection) -> int:
    """채점 시점이 도래한 픽의 T+N 종가를 채워 알파·적중을 갱신한다. 갱신 행 수 반환."""
    cutoff = (datetime.now(tz=UTC).date() - timedelta(days=MAX_BACKFILL_DAYS)).strftime("%Y-%m-%d")
    pending = store.fetch_pending(conn, since=cutoff)
    if not pending:
        return 0

    earliest = min(r["rec_date"] for r in pending)
    bstart = (datetime.strptime(earliest, "%Y-%m-%d").date() - timedelta(days=12)).strftime(
        "%Y-%m-%d"
    )
    bench = _bench_series(bstart)

    now = datetime.now(tz=UTC).isoformat()
    updated = 0
    for row in pending:
        rec_date = row["rec_date"]
        start = (datetime.strptime(rec_date, "%Y-%m-%d").date() - timedelta(days=10)).strftime(
            "%Y-%m-%d"
        )
        df = _download(row["ticker"], start)
        if df is None:
            continue

        series = _series_dict(df)
        dates = sorted(series)
        post = [d for d in dates if d >= rec_date]
        pre = [d for d in dates if d < rec_date]
        par = series[pre[-1]] if pre else row.get("price_at_rec")
        if par is None:
            continue

        bkey = _BENCH_KEY.get(row["scope"], "FOREIGN")
        bseries = bench.get(bkey, {})
        bbase = _bench_baseline(bseries, rec_date)

        patch: dict[str, Any] = {}
        for label, idx in DHORIZONS:
            if row.get(f"price_{label}") is not None:
                continue
            if idx >= len(post):
                continue
            end_date = post[idx]
            price = series[end_date]
            sh = score_horizon(_DIRECTION, par, price, bbase, _bench_on(bseries, end_date))
            if sh is None:
                continue
            patch[f"price_{label}"] = round(price, 4)
            patch[f"ret_{label}"] = sh["ret"]
            patch[f"bench_ret_{label}"] = sh["bench_ret"]
            patch[f"alpha_{label}"] = sh["alpha"]
            patch[f"hit_{label}"] = sh["hit"]

        if patch:
            patch["updated_at"] = now
            patch["benchmark"] = BENCH_SYMBOL.get(bkey)
            patch["price_at_rec"] = par
            store.update_outcome(conn, row["id"], patch)
            updated += 1

    log.info("discovery_outcomes 백필: %d건 갱신", updated)
    return updated


# ── 집계 리포트 ───────────────────────────────────────────────────────────────


def calibration_report(conn: Connection, since: str | None = None) -> dict[str, Any]:
    """호라이즌별 적중률·평균 알파를 집계한다(읽기 전용)."""
    rows = store.fetch_all(conn, since=since)
    out: dict[str, Any] = {"total": len(rows), "horizons": {}}
    for label, _ in DHORIZONS:
        hits = [r.get(f"hit_{label}") for r in rows if r.get(f"hit_{label}") is not None]
        alphas = [r.get(f"alpha_{label}") for r in rows if r.get(f"alpha_{label}") is not None]
        graded = len(hits)
        win = sum(1 for h in hits if h == 1)
        out["horizons"][label] = {
            "graded": graded,
            "hit_rate": round(win / graded, 3) if graded else None,
            "avg_alpha": round(sum(alphas) / len(alphas), 2) if alphas else None,
        }
    return out
