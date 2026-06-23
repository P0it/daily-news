"""아침 브리핑 파이프라인 전체 플로우."""

from __future__ import annotations

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from news_briefing.analysis.attention_phase import build_phase_map
from news_briefing.analysis.hot_issues import (
    analyze_hot_issues,
    analyze_hot_issues_domestic,
    foreign_news_weight,
)
from news_briefing.analysis.scoring import score_consensus, score_edgar, score_report, score_wire
from news_briefing.collectors.analyst_ratings import fetch_analyst_ratings
from news_briefing.collectors.base import CollectedItem
from news_briefing.collectors.congress_trades import fetch_congress_trades
from news_briefing.collectors.dart import fetch_dart_list
from news_briefing.collectors.edgar import fetch_all_edgar
from news_briefing.collectors.fda_approvals import fetch_fda_approvals
from news_briefing.collectors.gov_contracts import fetch_gov_contracts
from news_briefing.collectors.insider_cluster import fetch_insider_clusters
from news_briefing.collectors.institutional_13f import fetch_institutional_13f
from news_briefing.collectors.krx_etf import fetch_krx_etf
from news_briefing.collectors.macro import fetch_macro
from news_briefing.collectors.press_wire import fetch_press_wires
from news_briefing.collectors.research import fetch_research_reports
from news_briefing.collectors.rss import fetch_all_rss
from news_briefing.config import Config
from news_briefing.delivery.digest import format_digest, write_digest
from news_briefing.delivery.discord import send_message as discord_send
from news_briefing.delivery.json_builder import (
    build_briefing_json,
    write_briefing,
)
from news_briefing.storage.db import get_client
from news_briefing.storage.seen import batch_filter_unseen, batch_mark_seen
from news_briefing.storage.tickers import TickerRow, upsert_ticker

log = logging.getLogger(__name__)

MIN_SIGNAL_SCORE = 60  # SIGNALS.md 2.2

# 영어로 발행되는 해외 RSS 소스 — 해외 picks 보조 입력 판별용
_ENGLISH_SOURCES = frozenset(
    {
        "rss:bbc-world",
        "rss:bbc-business",
        "rss:ft-markets",
        "rss:marketwatch",
        "rss:gnews-world-en",
        "rss:gnews-business-en",
        "rss:gnews-tech-en",
        "rss:gnews-us-stocks-en",
        "rss:gnews-us-markets-en",
    }
)


@contextmanager
def _timed(label: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - t0
        log.info("[TIMER] %-40s %.1fs", label, elapsed)


@dataclass(frozen=True, slots=True)
class MorningResult:
    new_items: int
    signal_count: int
    picks_domestic: int
    picks_foreign: int
    digest_path: Path
    briefing_json_path: Path
    sent_discord: bool


def _send_discord(cfg: Config, text: str) -> bool:
    """내부 헬퍼. 테스트에서 mock patch 타겟."""
    if not cfg.discord_webhook_url:
        log.warning("DISCORD_WEBHOOK_URL 미설정, Discord 전송 스킵.")
        return False
    return discord_send(cfg.discord_webhook_url, text)


def _trigger_deploy(cfg: Config) -> bool:
    """Vercel Deploy Hook 을 호출해 배포 서버가 DB에서 다시 빌드하게 한다.

    DB(원본)는 이미 갱신됐으므로, 어느 생성 머신이든 이 신호만 보내면 배포본이
    최신화된다. 훅 URL 미설정 시 스킵(로컬 전용 머신 등)."""
    import requests  # noqa: PLC0415

    if not cfg.vercel_deploy_hook_url:
        log.info("VERCEL_DEPLOY_HOOK_URL 미설정, 배포 트리거 스킵.")
        return False
    try:
        resp = requests.post(cfg.vercel_deploy_hook_url, timeout=15)
        if resp.status_code in (200, 201):
            return True
        log.warning("deploy hook 응답 status=%s body=%s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        log.error("deploy hook 예외: %s", e)
        return False


def run_morning(
    cfg: Config,
    *,
    dry_run: bool = False,
    notify: bool = True,
    now: datetime | None = None,
) -> MorningResult:
    # notify=False 는 배포는 트리거하되 Discord 알림만 건너뛴다(조용한 재배포용).
    now = now or datetime.now()
    t_total = time.perf_counter()
    log.info("morning start date=%s dry_run=%s notify=%s", now.date(), dry_run, notify)

    conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
    try:
        # 0. 오래된 데이터 정리 (일회성 데이터, 매일 실행)
        from news_briefing.storage.cleanup import run_cleanup

        with _timed("0. cleanup"):
            run_cleanup(
                conn,
                digests_dir=cfg.digests_dir,
                briefings_dir=cfg.public_briefings_dir,
                today=now.date(),
            )

        # 1. 수집 (DART + RSS + EDGAR + 거시지표 + 리서치 + KRX ETF)
        # 아침 6시 브리핑은 '직전 거래일' 공시를 분석해야 한다. DART에 당일 공시는
        # 새벽엔 거의 안 올라오므로(행정성 몇 건뿐), 4일 룩백 윈도우로 직전 거래일을
        # 포함시킨다. 주말·공휴일은 윈도우가 자동 커버하고, 과거 실행분 중복은
        # seen 테이블 dedup이 거른다. (해외 EDGAR 등은 '최신 N건' 롤링이라 무관)
        date_key = now.strftime("%Y%m%d")
        dart_bgn = (now - timedelta(days=3)).strftime("%Y%m%d")
        with _timed("1. collect DART"):
            disclosures = fetch_dart_list(cfg.dart_api_key, dart_bgn, end_date=date_key)
        with _timed("1. collect RSS"):
            news = fetch_all_rss()
        with _timed("1. collect EDGAR"):
            edgar_items = fetch_all_edgar(cfg.edgar_user_agent) if cfg.edgar_user_agent else []
        with _timed("1. collect macro"):
            macro_indices = fetch_macro()
        with _timed("1. collect research"):
            research_raw = fetch_research_reports()
        with _timed("1. collect KRX ETF"):
            etf_snapshots = fetch_krx_etf()

        # 선행 지표 수집기 (실패해도 파이프라인 계속)
        gov_items: list = []
        with _timed("1. collect gov_contracts"):
            try:
                gov_items = fetch_gov_contracts()
            except Exception as e:
                log.warning("gov_contracts 수집 실패 (건너뜀): %s", e)

        cluster_items: list = []
        with _timed("1. collect insider_cluster"):
            try:
                if cfg.edgar_user_agent:
                    cluster_items = fetch_insider_clusters(cfg.edgar_user_agent)
            except Exception as e:
                log.warning("insider_cluster 수집 실패 (건너뜀): %s", e)

        # 1차 소스 신규 채널 — 종목추천 신뢰도용 (실패해도 파이프라인 계속)
        inst_items: list = []
        with _timed("1. collect institutional_13f"):
            try:
                if cfg.edgar_user_agent:
                    inst_items = fetch_institutional_13f(cfg.edgar_user_agent)
            except Exception as e:
                log.warning("institutional_13f 수집 실패 (건너뜀): %s", e)

        congress_items: list = []
        with _timed("1. collect congress_trades"):
            try:
                congress_items = fetch_congress_trades()
            except Exception as e:
                log.warning("congress_trades 수집 실패 (건너뜀): %s", e)

        fda_items: list = []
        with _timed("1. collect fda_approvals"):
            try:
                fda_items = fetch_fda_approvals()
            except Exception as e:
                log.warning("fda_approvals 수집 실패 (건너뜀): %s", e)

        wire_items: list = []
        with _timed("1. collect press_wire"):
            try:
                wire_items = fetch_press_wires()
            except Exception as e:
                log.warning("press_wire 수집 실패 (건너뜀): %s", e)

        analyst_items: list = []
        with _timed("1. collect analyst_ratings"):
            try:
                analyst_items = fetch_analyst_ratings(cfg.fmp_api_key)
            except Exception as e:
                log.warning("analyst_ratings 수집 실패 (건너뜀): %s", e)

        all_items = (
            disclosures
            + news
            + edgar_items
            + research_raw
            + gov_items
            + cluster_items
            + inst_items
            + congress_items
            + fda_items
            + wire_items
            + analyst_items
        )

        # 2. 중복 제거 (배치 조회) + DART tickers 매핑 자동 수집
        with _timed("2. dedup + seen"):
            unseen_pairs = set(batch_filter_unseen(conn, [(i.source, i.ext_id) for i in all_items]))
            new_items: list[CollectedItem] = [
                i for i in all_items if (i.source, i.ext_id) in unseen_pairs
            ]
            batch_mark_seen(conn, list(unseen_pairs))

        log.info("2. new_items=%d (total=%d)", len(new_items), len(all_items))

        # DART tickers 배치 upsert
        with _timed("2. upsert tickers"):
            for item in new_items:
                if item.source == "dart" and item.company_code:
                    corp_code = (item.extra or {}).get("corp_code", "")
                    if corp_code:
                        upsert_ticker(
                            conn,
                            TickerRow(
                                stock_code=item.company_code,
                                corp_code=corp_code,
                                corp_name=item.company or "",
                                market=None,
                            ),
                        )

        # 3. 점수 산정 (DART·EDGAR·와이어·pre_scored 분기)
        scored: list[tuple[CollectedItem, int, str]] = []
        for it in new_items:
            if it.kind != "disclosure":
                continue

            extra = it.extra or {}
            if extra.get("pre_scored") is not None:
                # 선행 지표·1차 소스 수집기 — 수집 시점에 이미 점수 산정
                # (gov_contracts·edgar_cluster·edgar_13f·congress_trades·fda·analyst)
                s = int(extra["pre_scored"])
                d = extra.get("direction", "positive")
            elif it.source == "edgar":
                form_type = extra.get("form_type", "")
                items_str = extra.get("items", "")
                s, d = score_edgar(form_type=form_type, items=items_str)
            elif it.source.startswith("wire:"):
                s, d = score_wire(it.title)
            else:
                s, d = score_report(it.title)
            scored.append((it, s, d))

        # 4. 뉴스 분리 — 표시하지 않고 picks 추론 보조 입력으로만 사용
        from news_briefing.collectors.rss import SOURCE_META

        stock_news_domestic: list[CollectedItem] = []
        stock_news_foreign: list[CollectedItem] = []
        intl_news_foreign: list[CollectedItem] = []  # 영어권 국제 시사 — 해외 picks 입력
        for it in new_items:
            if it.kind != "news":
                continue
            category = (it.extra or {}).get("category", "")
            if category in ("stock", ""):
                scope, _ = SOURCE_META.get(it.source, ("domestic", "stock"))
                if scope == "foreign":
                    stock_news_foreign.append(it)
                else:
                    stock_news_domestic.append(it)
            elif category == "international" and it.source in _ENGLISH_SOURCES:
                intl_news_foreign.append(it)
            # politics·society·tech·ai 는 종목추천과 무관 — 무시(표시 제거)

        # research 아이템 점수 산정 (신규 아이템만, category=="research" 분기)
        MIN_RESEARCH_SCORE = 60  # 유지(42)는 제외, 상향/하향/신규만 노출
        research_scored: list[tuple[CollectedItem, int, str]] = []
        for it in new_items:
            if (it.extra or {}).get("category") != "research":
                continue
            tp_dir = (it.extra or {}).get("tpDirection", "유지")
            tp_pct = float((it.extra or {}).get("targetPricePct", 0))
            s, d = score_consensus(tp_dir, tp_pct)
            if s >= MIN_RESEARCH_SCORE:
                research_scored.append((it, s, d))
        research_scored.sort(key=lambda t: t[1], reverse=True)
        research_scored = research_scored[:15]  # 상위 15건만

        # 5. 디지스트 텍스트 백업 (시그널 위주, 뉴스 제거)
        with _timed("5. digest write"):
            text = format_digest(
                date=now, scored_signals=scored, news=[], min_score=MIN_SIGNAL_SCORE
            )
            digest_path = write_digest(digests_dir=cfg.digests_dir, date=now, text=text)

        # 6. 주목도 위상 분류 — hot_issues 선정에 P1·P2 우선 기준으로 사용
        phase_map: dict = {}
        with _timed("6. attention phase"):
            try:
                phase_map = build_phase_map(scored, enable_price=True, enable_gtrends=False)
                log.info("attention phase 분류 완료: %d건", len(phase_map))
            except Exception as e:
                log.warning("attention phase 분류 실패 (건너뜀): %s", e)

        # phase_map을 {ext_id: phase_int} 형태로 변환
        phase_int_map: dict[str, int] = {k: v.phase for k, v in phase_map.items()}

        # 7. 오늘의 핵심 이슈 선정 — 해외·국내 병렬 실행
        # 해외 종목 후보 — 점수 척도를 하나로 통일:
        #   공시(EDGAR·gov)는 내용 기반 실제 점수, 뉴스는 소스 신뢰도 기반 점수.
        #   curation_score(시간 감쇠)를 버려 '방금 올라온 기사'가 상위를 잠식하지 않는다.
        _FOREIGN_DISCLOSURE_SOURCES = {
            "edgar",
            "edgar_13f",
            "edgar_cluster",
            "gov_contracts",
            "congress_trades",
            "fda",
            "analyst",
        }
        foreign_candidates: list[tuple[CollectedItem, int]] = []
        for it, s, _d in scored:
            if it.source in _FOREIGN_DISCLOSURE_SOURCES or it.source.startswith("wire:"):
                foreign_candidates.append((it, s))
        for it in stock_news_foreign:
            foreign_candidates.append((it, foreign_news_weight(it.source)))
        # 영어권 국제 시사 뉴스(BBC World 등)만 — 해외 picks 보조 입력
        for it in intl_news_foreign:
            foreign_candidates.append((it, foreign_news_weight(it.source)))

        # 국내 picks 촉매는 DART 공시만 쓴다. 증권사 리포트(research_scored)는
        # 이미 애널리스트가 공개 분석한 '늦은' 직접 신호라 picks 트리거로 쓰면
        # 알파가 없다 — picks 입력에서 디커플링(DECISIONS #17). 수집·표시는 유지하고,
        # 향후 테마 밀도/수혜주 단서 용도로만 재배치 예정.
        domestic_candidates: list[tuple[CollectedItem, int]] = []
        for it, s, _d in scored:
            if it.source == "dart":
                domestic_candidates.append((it, s))
        for it in stock_news_domestic:
            domestic_candidates.append((it, 40))

        hot_issues_foreign: list[dict] = []
        hot_issues_domestic: list[dict] = []

        # 병렬 실행: 두 Opus(+thinking) 호출을 동시에 던진다. 통제 측정 결과
        # 동시 2개도 각 ~110s 로 단독(~136s)과 동등 — Max 처리량 경합은 이 규모에서
        # 발생하지 않는다. 병렬이 순차(합 ~250s)보다 빠르므로 병렬을 유지한다.
        # (과거 타임아웃은 병렬 탓이 아니라 일시적 서버 지연 + thinking 변동성이었고,
        #  방어책은 _call_claude timeout 상향(420s)으로 둔다.)
        def _run_foreign() -> list[dict]:
            return analyze_hot_issues(foreign_candidates, phase_map=phase_int_map)

        def _run_domestic() -> list[dict]:
            return analyze_hot_issues_domestic(domestic_candidates, phase_map=phase_int_map)

        with _timed("7. hot_issues (foreign+domestic 병렬)"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_foreign = pool.submit(_run_foreign)
                fut_domestic = pool.submit(_run_domestic)
                for fut in as_completed([fut_foreign, fut_domestic]):
                    label = "foreign" if fut is fut_foreign else "domestic"
                    try:
                        result = fut.result()
                        if fut is fut_foreign:
                            hot_issues_foreign = result
                        else:
                            hot_issues_domestic = result
                    except Exception as e:
                        log.warning("hot_issues(%s) 분석 실패: %s", label, e)

        # 7a. picks 사실 검증 — 환각 종목 제거 + 티커 실존 확인 (실패해도 원본 유지)
        with _timed("7a. pick verify"):
            try:
                from news_briefing.analysis.pick_verify import apply_verification

                # 검증기에 점수순으로 넘긴다. 수집 순서대로 넘기면 고득점 촉매
                # 공시가 [:120] 밖으로 밀려 'grounded=false' 오탐이 났다(예: 합병
                # 공시를 못 봐 환각으로 오판). 점수 desc 정렬로 핵심 공시를 보장.
                foreign_evidence = [
                    f"[{it.source}] {it.company or ''} {it.title}".strip()
                    for it, _ in sorted(foreign_candidates, key=lambda x: x[1], reverse=True)
                ]
                domestic_evidence = [
                    f"[{it.source}] {it.company or ''} {it.title}".strip()
                    for it, _ in sorted(domestic_candidates, key=lambda x: x[1], reverse=True)
                ]
                if hot_issues_foreign:
                    hot_issues_foreign = apply_verification(
                        hot_issues_foreign,
                        scope="foreign",
                        conn=conn,
                        evidence_lines=foreign_evidence,
                        fmp_api_key=cfg.fmp_api_key,
                    )
                if hot_issues_domestic:
                    hot_issues_domestic = apply_verification(
                        hot_issues_domestic,
                        scope="domestic",
                        conn=conn,
                        evidence_lines=domestic_evidence,
                        fmp_api_key=cfg.fmp_api_key,
                    )
            except Exception as e:
                log.warning("pick 검증 실패 (원본 유지): %s", e)

        # 7a-2. 관찰 리스트 — 픽이 0인 scope 만, 그날 점수 상위 공시를 보조 표시.
        #   강한 촉매 없는 날 완전 빈 화면 대신 '지켜볼 만한 것'을 보여준다(픽과 분리).
        watchlist_foreign: list[dict] = []
        watchlist_domestic: list[dict] = []
        with _timed("7a-2. watchlist"):
            try:
                from news_briefing.analysis.watchlist import select_watchlist

                if not hot_issues_foreign:
                    watchlist_foreign = select_watchlist(scored, foreign=True)
                if not hot_issues_domestic:
                    watchlist_domestic = select_watchlist(scored, foreign=False)
                log.info(
                    "watchlist: foreign %d, domestic %d",
                    len(watchlist_foreign),
                    len(watchlist_domestic),
                )
            except Exception as e:
                log.warning("watchlist 생성 실패 (건너뜀): %s", e)

        # 7a-3. 낙수효과 수혜주 — 관찰 이벤트가 경쟁사·대체재에 주는 반사이익(추론).
        #   정식 픽과 분리된 저컨빅션 보조 레이어. 실패해도 관찰은 그대로 표시.
        with _timed("7a-3. spillover"):
            try:
                from news_briefing.analysis.spillover import analyze_spillover

                if watchlist_foreign:
                    watchlist_foreign = analyze_spillover(watchlist_foreign, scope="foreign")
                if watchlist_domestic:
                    watchlist_domestic = analyze_spillover(watchlist_domestic, scope="domestic")
            except Exception as e:
                log.warning("spillover 분석 실패 (관찰 원본 유지): %s", e)

        # 7b. Briefing JSON (picks 중심 — 뉴스·시그널 표시 제거)
        with _timed("7b. build+write briefing JSON"):
            briefing = build_briefing_json(
                date=now,
                hot_issues_foreign=hot_issues_foreign,
                hot_issues_domestic=hot_issues_domestic,
                watchlist_foreign=watchlist_foreign,
                watchlist_domestic=watchlist_domestic,
                macro_indices=macro_indices,
                research_scored=research_scored,
                etf_snapshots=etf_snapshots,
            )
            briefing_json_path = write_briefing(
                public_briefings_dir=cfg.public_briefings_dir, briefing=briefing
            )

        # 7c. Supabase briefings 테이블에 저장 (원본 보관소) + 최근치 로컬 복원.
        #     프론트엔드는 로컬 정적 파일만 읽고, cleanup(step 0)은 최근 N일만
        #     남기므로, DB에서 같은 기간을 로컬로 복원해 달력에 과거 날짜를 채운다.
        with _timed("7c. upsert + export briefing"):
            try:
                from news_briefing.storage.briefings import (
                    export_briefings_to_local,
                    upsert_briefing,
                )
                from news_briefing.storage.cleanup import BRIEFINGS_KEEP_DAYS

                upsert_briefing(conn, briefing["date"], briefing)
                log.info("briefing upserted to Supabase: %s", briefing["date"])
                exported = export_briefings_to_local(
                    conn, cfg.public_briefings_dir, keep_days=BRIEFINGS_KEEP_DAYS
                )
                log.info("briefing 로컬 복원: %d일치", len(exported))
            except Exception as e:
                log.warning("briefing Supabase 저장/복원 실패: %s", e)

        # 7d. picks 성과 히스토리 갱신 + DB 저장 (배포 빌드가 여기서 복원)
        with _timed("7d. picks history update"):
            try:
                import json as _json  # noqa: PLC0415

                from news_briefing.analysis.picks_tracker import (  # noqa: PLC0415
                    PICKS_HISTORY_PATH,
                    load_briefings_from_supabase,
                    update_history,
                )
                from news_briefing.storage.picks_history import (  # noqa: PLC0415
                    upsert_picks_history,
                )

                recent_briefings = load_briefings_from_supabase(limit=30)
                update_history(recent_briefings)
                # 로컬 파일을 원본(DB)으로 승격 — 여러 머신이 같은 행을 갱신한다.
                ph_data = _json.loads(PICKS_HISTORY_PATH.read_text(encoding="utf-8"))
                upsert_picks_history(conn, ph_data)
                log.info("picks_history 갱신 + DB 저장 완료")
            except Exception as e:
                log.warning("picks 히스토리 갱신 실패: %s", e)

        # 7e. pick_outcomes 영구 원장 — 신규 픽 스냅샷 + 채점 시점 도래분 백필.
        #     실적 탭(30일 실시간)과 별개로, 촉매별 적중률(재학습 데이터)을 영구 축적한다.
        with _timed("7e. pick outcomes ledger"):
            try:
                from news_briefing.analysis.picks_outcomes import (  # noqa: PLC0415
                    backfill_outcomes,
                    record_outcomes,
                )

                snapped = record_outcomes(conn, briefing)
                graded = backfill_outcomes(conn)
                log.info("pick_outcomes: 스냅샷 %d건, 채점 갱신 %d건", snapped, graded)
            except Exception as e:
                log.warning("pick_outcomes 원장 갱신 실패: %s", e)

        # 8. RAG 자동 인덱싱 (Week 4) — 실패해도 morning 전체 중단 X
        with _timed("8. RAG indexing"):
            try:
                from news_briefing.analysis.rag import index_briefing

                indexed = index_briefing(
                    conn, briefing_json_path, embed_model=cfg.ollama_embed_model
                )
                if indexed > 0:
                    log.info("RAG 인덱싱: %d 신규 문서", indexed)
            except Exception as e:
                log.warning("RAG 인덱싱 실패: %s", e)

        # 9. 카톡 전송 (dry-run 아닐 때)
        sent = False
        sig_above = sum(1 for _, s, _ in scored if s >= MIN_SIGNAL_SCORE)
        log.info("[TIMER] %-40s %.1fs", "TOTAL", time.perf_counter() - t_total)
        # picks는 hot_issues 각 이슈의 picks 배열에 들어있으므로 종목 수를 합산한다.
        picks_domestic = sum(len(iss.get("picks") or []) for iss in hot_issues_domestic)
        picks_foreign = sum(len(iss.get("picks") or []) for iss in hot_issues_foreign)

        if not dry_run:
            # DB가 갱신됐으니 배포 서버가 빌드시 다시 끌어가도록 재배포 트리거.
            with _timed("9. trigger deploy"):
                if _trigger_deploy(cfg):
                    log.info("Vercel 재배포 트리거 완료")

            if notify:
                link_url = f"{cfg.vercel_base_url}/?scope=foreign"
                message = (
                    f"**오늘의 종목추천 · {now.strftime('%m월 %d일')}**\n"
                    f"해외 {picks_foreign}종목 · 국내 {picks_domestic}종목 (공시 {sig_above}건)\n"
                    f"{link_url}"
                )
                sent = _send_discord(cfg, message)
            else:
                log.info("notify=False, Discord 알림 스킵 (배포만 수행).")
        else:
            sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))

        return MorningResult(
            new_items=len(new_items),
            signal_count=sig_above,
            picks_domestic=picks_domestic,
            picks_foreign=picks_foreign,
            digest_path=digest_path,
            briefing_json_path=briefing_json_path,
            sent_discord=sent,
        )
    finally:
        conn.close()
