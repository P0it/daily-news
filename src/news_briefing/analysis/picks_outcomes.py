"""추천 픽 영구 원장 + T+1/T+5/T+20 적중 라벨링.

picks_tracker(실적 탭용 실시간 수익률, 30일 폐기)와 별개로, 픽 1건마다 예측 방향·
촉매·근거를 영구 보관하고 고정 시점 수익률을 채점한다. 이렇게 쌓인 '우리만의 적중률
데이터'가 이후 픽 생성 프롬프트의 calibration 근거가 된다(Phase 2).

흐름:
  1) record_outcomes  — morning 실행 시 신규 픽을 원장에 스냅샷(채점 시점은 null).
  2) backfill_outcomes — 매 실행마다 거래일이 충분히 지난 픽의 T+N 종가를 채워 채점.
  3) calibration_report — 촉매/방향/소스별 적중률 집계(읽기 전용).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import yfinance as yf

from news_briefing.analysis.picks_tracker import _yf_ticker, fetch_prev_close
from news_briefing.storage import picks_outcomes as store
from news_briefing.storage.db import Connection

log = logging.getLogger(__name__)

# 채점 시점: (라벨, 진입 기준가 대비 N번째 거래일 종가의 0-based 위치).
# idx=0 → 추천일 당일 종가(= 진입 기준가 다음 거래일), idx=4 → 5거래일, idx=19 → 20거래일.
HORIZONS: list[tuple[str, int]] = [("1d", 0), ("5d", 4), ("20d", 19)]

# 알파(초과수익) 판정 데드밴드(%). 이 범위 안의 초과수익은 노이즈로 보고 미판정(null).
DEAD_BAND_PCT = 1.0

# 너무 오래된 픽은 가격 백필 재시도 중단(상장폐지·티커 변경 등으로 영영 안 채워질 수 있음).
MAX_BACKFILL_DAYS = 45

# scope/상장 시장 → 벤치마크 지수. 국내는 .KS/.KQ 별로, 해외는 S&P500 기준.
# "진짜 촉매면 시장이 빠져도 오른다" — 절대수익이 아닌 지수 대비 초과수익으로 채점한다.
BENCH_SYMBOL: dict[str, str] = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "FOREIGN": "^GSPC",
}


# ── 적중 라벨링 (알파 기준) ───────────────────────────────────────────────────


def label_hit(direction: str | None, alpha: float | None) -> int | None:
    """예측 방향과 **알파(지수 대비 초과수익, %)**로 적중 여부를 라벨링한다.

    절대수익이 아니라 알파로 판정하는 이유: 시장이 빠진 날 같이 빠진 건 촉매 실패가
    아닐 수도, 시장이 오른 날 같이 오른 건 촉매 성공이 아닐 수도 있다. 진짜 촉매라면
    시장 방향과 무관하게 독립적인 초과수익을 내야 한다.

    - positive: alpha > +데드밴드 → 적중(1)  (시장을 이김), alpha < -데드밴드 → 실패(0)
    - negative: 반대 (시장보다 더 빠지면 적중)
    - mixed/그 외/데드밴드 이내/alpha None → 미판정(None)
    """
    if alpha is None or direction not in ("positive", "negative"):
        return None
    if abs(alpha) < DEAD_BAND_PCT:
        return None
    if direction == "positive":
        return 1 if alpha > 0 else 0
    return 1 if alpha < 0 else 0


def score_horizon(
    direction: str | None,
    price_at_rec: float | None,
    stock_close: float | None,
    bench_baseline: float | None,
    bench_close: float | None,
) -> dict[str, Any] | None:
    """한 채점 시점의 절대수익·벤치마크수익·알파·적중(알파 기준)을 계산한다.

    벤치마크 데이터가 없으면 alpha/hit 은 None(알파 없이 적중을 판정하지 않는다 —
    시장 탓/실력을 가르는 게 핵심이므로 벤치 없는 채점은 보류).
    """
    if not price_at_rec or price_at_rec <= 0 or stock_close is None:
        return None
    ret = (stock_close / price_at_rec - 1) * 100
    bench_ret: float | None = None
    alpha: float | None = None
    if bench_baseline and bench_baseline > 0 and bench_close is not None:
        bench_ret = (bench_close / bench_baseline - 1) * 100
        alpha = ret - bench_ret
    return {
        "ret": round(ret, 2),
        "bench_ret": round(bench_ret, 2) if bench_ret is not None else None,
        "alpha": round(alpha, 2) if alpha is not None else None,
        "hit": label_hit(direction, alpha),
    }


# ── 원장 스냅샷 (추천 시점) ───────────────────────────────────────────────────


def extract_outcome_rows(briefing: dict[str, Any]) -> list[dict[str, Any]]:
    """브리핑 dict 에서 픽을 원장 행(채점 시점 null)으로 변환한다."""
    date_str: str = briefing.get("date", "")
    if not date_str:
        return []
    economy = briefing.get("tabs", {}).get("economy", {})
    hot_issues = economy.get("hotIssues", {})
    now = datetime.now(tz=UTC).isoformat()

    rows: list[dict[str, Any]] = []
    for scope in ("domestic", "foreign"):
        for issue in hot_issues.get(scope, []):
            theme = issue.get("asset", "")
            direction = issue.get("direction", "")
            signal = issue.get("signal", "")
            for pick in issue.get("picks") or []:
                ticker = (pick.get("ticker") or "").strip()
                if not ticker:
                    continue
                rows.append(
                    {
                        "id": f"{date_str}-{scope}-{ticker}",
                        "rec_date": date_str,
                        "ticker": ticker,
                        "name": pick.get("name", ticker),
                        "scope": scope,
                        "direction": direction,
                        "signal": signal,
                        "theme": theme,
                        "rationale": pick.get("description", ""),
                        "consensus_risk": pick.get("consensus_risk"),
                        "verify_status": pick.get("verifyStatus"),
                        "is_filer": 1 if pick.get("isFiler") else 0,
                        "currency": "USD" if scope == "foreign" else "KRW",
                        "price_at_rec": None,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
    return rows


def record_outcomes(conn: Connection, briefing: dict[str, Any]) -> int:
    """브리핑의 신규 픽을 원장에 스냅샷한다. 기록한 신규 행 수를 반환.

    이미 존재하는 id 는 건드리지 않는다(재실행 시 채점 데이터·created_at 보존).
    진입 기준가는 picks_history(같은 실행에서 먼저 갱신됨)에서 재사용하고,
    없으면 fetch_prev_close 로 보충한다.
    """
    rows = extract_outcome_rows(briefing)
    if not rows:
        return 0

    existing = store.fetch_existing_ids(conn, [r["id"] for r in rows])
    new_rows = [r for r in rows if r["id"] not in existing]
    if not new_rows:
        return 0

    prev_close = _prev_close_lookup()
    for r in new_rows:
        par = prev_close.get((r["rec_date"], r["ticker"]))
        if par is None:
            par = fetch_prev_close(r["ticker"], r["scope"], r["rec_date"])
        r["price_at_rec"] = par

    store.upsert_outcomes(conn, new_rows)
    log.info("pick_outcomes 스냅샷: 신규 %d건", len(new_rows))
    return len(new_rows)


def seed_outcomes(conn: Connection, briefings: list[dict[str, Any]]) -> int:
    """과거 브리핑 목록을 원장에 일괄 스냅샷한다(최초 1회 백필 시드용).

    이미 있는 id 는 record_outcomes 가 건너뛰므로 반복 실행해도 안전하다.
    신규로 기록한 총 행 수를 반환.
    """
    total = 0
    for b in briefings:
        try:
            total += record_outcomes(conn, b)
        except Exception as e:
            log.warning("seed 실패 (%s): %s", b.get("date"), e)
    return total


def _prev_close_lookup() -> dict[tuple[str, str], float]:
    """이미 생성된 picks_history.json 에서 (date, ticker)→priceAtRec 매핑을 만든다.

    같은 morning 실행에서 picks_tracker 가 직전 거래일 종가를 이미 받아왔으므로,
    yfinance 중복 호출을 피하려 재사용한다. 파일이 없으면 빈 매핑.
    """
    import json

    from news_briefing.analysis.picks_tracker import PICKS_HISTORY_PATH

    out: dict[tuple[str, str], float] = {}
    try:
        data = json.loads(PICKS_HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return out
    for rec in data.get("records", []):
        par = rec.get("priceAtRec")
        if par is not None:
            out[(rec.get("date", ""), rec.get("ticker", ""))] = par
    return out


# ── 채점 백필 (T+N 종가) ─────────────────────────────────────────────────────


def _download_window(ticker: str, scope: str, start: str) -> tuple[Any, str | None]:
    """start~오늘 일별 종가 df 와 **실제 매칭된 심볼**을 반환.

    매칭 심볼의 접미사(.KS/.KQ)로 상장 시장을 알 수 있어 벤치마크 선택에 쓴다.
    국내는 .KS/.KQ 후보를 모두 받아 진짜 listing 을 고른다. .KS 를 먼저 채택하면
    코스닥 종목에도 유령·낡은 데이터가 잡혀 board(=벤치마크)와 가격이 함께 틀어진다.
    가장 최신 거래일까지 있고 행이 많은 listing = 실제 활성 상장으로 본다.
    """
    today = datetime.now(tz=UTC).date()
    end = (today + timedelta(days=1)).strftime("%Y-%m-%d")  # end 는 exclusive
    candidates: list[tuple[str, int, Any, str]] = []
    for yt in _yf_ticker(ticker, scope):
        try:
            df = yf.download(yt, start=start, end=end, progress=False, auto_adjust=True)
        except Exception:
            df = None
        if df is not None and not df.empty:
            candidates.append((str(df.index[-1])[:10], len(df), df, yt))
    if not candidates:
        return None, None
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    best = candidates[0]
    return best[2], best[3]


def _benchmark_key(scope: str, matched_symbol: str | None) -> str:
    """scope·매칭 심볼로 벤치마크 키를 정한다."""
    if scope == "foreign":
        return "FOREIGN"
    if matched_symbol and matched_symbol.endswith(".KQ"):
        return "KOSDAQ"
    return "KOSPI"  # .KS 또는 미상 → 코스피


def _series_dict(df: Any) -> dict[str, float]:
    """yfinance df 를 {YYYY-MM-DD: 종가} 매핑으로 변환(멀티인덱스 대응)."""
    out: dict[str, float] = {}
    if df is None or df.empty:
        return out
    close = df["Close"]
    for i in range(len(df)):
        d = str(df.index[i])[:10]
        val = close.iloc[i]
        if hasattr(val, "iloc"):
            val = val.iloc[0]
        try:
            out[d] = float(val)
        except (TypeError, ValueError):
            continue
    return out


def _bench_series(start: str) -> dict[str, dict[str, float]]:
    """벤치마크 3종을 한 번씩만 받아 {키: {date: close}} 로 반환."""
    today = datetime.now(tz=UTC).date()
    end = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    out: dict[str, dict[str, float]] = {}
    for key, sym in BENCH_SYMBOL.items():
        try:
            df = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
        except Exception:
            df = None
        out[key] = _series_dict(df)
    return out


def _bench_baseline(series: dict[str, float], rec_date: str) -> float | None:
    """진입 기준일(추천일 직전 거래일)의 지수값 = rec_date 미만 마지막 날 종가."""
    dates = sorted(d for d in series if d < rec_date)
    return series[dates[-1]] if dates else None


def _bench_on(series: dict[str, float], date_str: str) -> float | None:
    """해당 일자(없으면 그 이전 마지막 거래일)의 지수값."""
    if date_str in series:
        return series[date_str]
    dates = sorted(d for d in series if d <= date_str)
    return series[dates[-1]] if dates else None


def _close_at_idx(df: Any, idx: int) -> float | None:
    """df 의 idx(0-based) 행 종가. 행이 부족하면 None(아직 그 시점 미도래)."""
    if df is None or df.empty or len(df) <= idx:
        return None
    try:
        if hasattr(df.columns, "levels"):
            val = df["Close"].iloc[idx]
            if hasattr(val, "iloc"):
                val = val.iloc[0]
            return float(val)
        if "Close" not in df.columns:
            return None
        return float(df["Close"].iloc[idx])
    except Exception:
        return None


def backfill_outcomes(conn: Connection) -> int:
    """채점 시점이 도래한 픽의 T+N 종가를 채워 수익률·적중을 갱신한다.

    price_20d 가 아직 비어있는(= 채점 미완) 행만 대상으로 하고, 행마다 yfinance
    창을 한 번만 받아 세 시점을 모두 처리한다. 갱신한 행 수를 반환.
    """
    cutoff = (datetime.now(tz=UTC).date() - timedelta(days=MAX_BACKFILL_DAYS)).strftime("%Y-%m-%d")
    pending = store.fetch_pending(conn, since=cutoff)
    if not pending:
        return 0

    # 벤치마크 3종을 한 번만 받아 재사용(가장 이른 추천일 직전부터 충분히).
    earliest = min(r["rec_date"] for r in pending)
    bstart = (datetime.strptime(earliest, "%Y-%m-%d").date() - timedelta(days=12)).strftime(
        "%Y-%m-%d"
    )
    bench = _bench_series(bstart)

    now = datetime.now(tz=UTC).isoformat()
    updated = 0
    for row in pending:
        rec_date = row["rec_date"]
        # 추천일 직전부터 받아, 기준가와 시점가를 같은(올바른) listing 으로 자기일관 계산.
        start = (datetime.strptime(rec_date, "%Y-%m-%d").date() - timedelta(days=10)).strftime(
            "%Y-%m-%d"
        )
        df, matched = _download_window(row["ticker"], row["scope"], start)
        if df is None:
            continue

        series = _series_dict(df)
        dates = sorted(series)
        post = [d for d in dates if d >= rec_date]  # 추천일 이후 거래일(채점 시점들)
        pre = [d for d in dates if d < rec_date]
        # 진입 기준가 = 같은 listing 의 추천일 직전 종가(자기일관). 없으면 저장값/보충.
        par = series[pre[-1]] if pre else (row.get("price_at_rec"))
        if par is None:
            par = fetch_prev_close(row["ticker"], row["scope"], rec_date)
        if par is None:
            continue

        bkey = _benchmark_key(row["scope"], matched)
        bseries = bench.get(bkey, {})
        bbase = _bench_baseline(bseries, rec_date)

        patch: dict[str, Any] = {}
        for label, idx in HORIZONS:
            if row.get(f"price_{label}") is not None:
                continue  # 이미 채점된 시점은 유지
            if idx >= len(post):
                continue  # 아직 그 거래일 미도래
            end_date = post[idx]
            price = series[end_date]
            sh = score_horizon(
                row.get("direction"), par, price, bbase, _bench_on(bseries, end_date)
            )
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

    if updated:
        log.info("pick_outcomes 백필: %d건 채점 갱신(알파 기준)", updated)
    return updated


# ── 적중률 집계 (calibration) ────────────────────────────────────────────────


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """한 그룹의 시점별 표본수·적중률(알파 기준)·평균 알파·평균 절대수익을 집계한다."""
    out: dict[str, Any] = {"n": len(rows)}
    for label, _ in HORIZONS:
        hits = [r[f"hit_{label}"] for r in rows if r.get(f"hit_{label}") is not None]
        alphas = [r[f"alpha_{label}"] for r in rows if r.get(f"alpha_{label}") is not None]
        rets = [r[f"ret_{label}"] for r in rows if r.get(f"ret_{label}") is not None]
        out[label] = {
            "graded": len(hits),
            "hit_rate": round(sum(hits) / len(hits), 3) if hits else None,
            "avg_alpha": round(sum(alphas) / len(alphas), 2) if alphas else None,
            "avg_ret": round(sum(rets) / len(rets), 2) if rets else None,
        }
    return out


def calibration_report(conn: Connection, since: str | None = None) -> dict[str, dict[str, Any]]:
    """촉매/방향/소스 차원별 적중률 리포트(읽기 전용)를 만든다.

    재학습 데이터의 사람이 읽는 요약. 'positive 인데 떨어진' 비율, 어떤 촉매가
    실제로 먹히는지를 한눈에 본다. Phase 2 에서 이 요약을 프롬프트에 주입한다.
    """
    rows = store.fetch_all(conn, since=since)
    report: dict[str, dict[str, Any]] = {"overall": _summarize(rows)}

    for dim in ("direction", "scope", "consensus_risk", "verify_status", "signal"):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            key = r.get(dim) or "—"
            groups[key].append(r)
        report[f"by_{dim}"] = {k: _summarize(v) for k, v in sorted(groups.items())}

    return report


def format_report(report: dict[str, dict[str, Any]]) -> str:
    """calibration_report 결과를 콘솔용 텍스트로 포매팅한다."""
    lines: list[str] = []

    def fmt_row(label: str, s: dict[str, Any]) -> str:
        cells = []
        for h, _ in HORIZONS:
            d = s.get(h, {})
            hr = d.get("hit_rate")
            al = d.get("avg_alpha")
            hr_s = f"{hr * 100:.0f}%" if hr is not None else "—"
            al_s = f"{al:+.1f}%" if al is not None else "—"
            cells.append(f"{h} 적중{hr_s}/α{al_s}({d.get('graded', 0)})")
        return f"  {label:<16} n={s.get('n', 0):<3} " + "  ".join(cells)

    overall = report.get("overall", {})
    lines.append("■ 전체 (적중=지수 대비 알파 기준)")
    lines.append(fmt_row("(all)", overall))

    titles = {
        "by_direction": "방향(예측)",
        "by_scope": "시장",
        "by_consensus_risk": "consensus_risk",
        "by_verify_status": "검증 상태",
        "by_signal": "촉매(signal)",
    }
    for dim, title in titles.items():
        groups = report.get(dim, {})
        if not groups:
            continue
        lines.append("")
        lines.append(f"■ {title}별")
        for key, s in groups.items():
            lines.append(fmt_row(str(key)[:16], s))

    return "\n".join(lines)
