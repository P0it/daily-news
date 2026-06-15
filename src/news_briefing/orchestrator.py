"""아침 브리핑 파이프라인 전체 플로우."""

from __future__ import annotations

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from news_briefing.analysis.attention_phase import build_phase_map
from news_briefing.analysis.curation import curation_score
from news_briefing.analysis.glossary import detect_term, ensure_glossary_entry
from news_briefing.analysis.hot_issues import (
    analyze_hot_issues,
    analyze_hot_issues_domestic,
    foreign_news_weight,
)
from news_briefing.analysis.llm import summarize_batch, translate_batch
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
from news_briefing.collectors.krx_etf import ETFSnapshot, fetch_krx_etf
from news_briefing.collectors.macro import fetch_macro
from news_briefing.collectors.press_wire import fetch_press_wires
from news_briefing.collectors.research import fetch_research_reports
from news_briefing.collectors.rss import fetch_all_rss
from news_briefing.config import Config
from news_briefing.delivery.digest import format_digest, write_digest
from news_briefing.delivery.discord import send_message as discord_send
from news_briefing.delivery.json_builder import (
    build_briefing_json,
    select_displayed_current,
    write_briefing,
)
from news_briefing.storage.db import get_client
from news_briefing.storage.seen import batch_filter_unseen, batch_mark_seen
from news_briefing.storage.tickers import TickerRow, upsert_ticker

log = logging.getLogger(__name__)

MIN_SIGNAL_SCORE = 60  # SIGNALS.md 2.2


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
    news_count: int
    current_count: int  # 시사 뉴스 수집 건수 (Week 3)
    ai_count: int  # AI 뉴스 수집 건수 (Week 5b)
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


def run_morning(
    cfg: Config, *, dry_run: bool = False, now: datetime | None = None
) -> MorningResult:
    now = now or datetime.now()
    t_total = time.perf_counter()
    log.info("morning start date=%s dry_run=%s", now.date(), dry_run)

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
        date_key = now.strftime("%Y%m%d")
        with _timed("1. collect DART"):
            disclosures = fetch_dart_list(cfg.dart_api_key, date_key)
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

        # 3. 점수 + glossary term 감지 (DART + EDGAR 분기)
        scored: list[tuple[CollectedItem, int, str]] = []
        term_ids_by_id: dict[str, str] = {}
        glossary_map: dict[str, dict] = {}
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

            # glossary 는 국내 공시만 (EDGAR 해설은 Week 3+ 로 이관)
            if it.source == "dart":
                term_id = detect_term(it.title)
                if term_id:
                    term_ids_by_id[it.ext_id] = term_id
                    if term_id not in glossary_map:
                        entry = ensure_glossary_entry(conn, term_id, lang="ko")
                        if entry:
                            glossary_map[term_id] = {
                                "shortLabel": entry.short_label,
                                "explanation": entry.explanation,
                                "direction": entry.signal_direction,
                            }

        # 4. 뉴스 카테고리별 분리 + 시사 큐레이션 + 시사 용어 감지
        from news_briefing.collectors.rss import SOURCE_META

        stock_news_domestic: list[CollectedItem] = []
        stock_news_foreign: list[CollectedItem] = []
        current_candidates: list[tuple[CollectedItem, int]] = []
        ai_news: list[CollectedItem] = []
        for it in new_items:
            if it.kind != "news":
                continue
            category = (it.extra or {}).get("category", "")
            if category == "ai":
                ai_news.append(it)
            elif category == "stock" or category == "":
                scope, _ = SOURCE_META.get(it.source, ("domestic", "stock"))
                if scope == "foreign":
                    stock_news_foreign.append(it)
                else:
                    stock_news_domestic.append(it)
            elif category in ("politics", "society", "international", "tech"):
                cs = curation_score(
                    source=it.source,
                    published_at=it.published_at,
                    now=now,
                    importance=1.0,
                )
                # 시사 용어 감지 (Week 3 F32)
                cur_term = detect_term(it.title)
                if cur_term:
                    term_ids_by_id[it.ext_id] = cur_term
                    if cur_term not in glossary_map:
                        entry = ensure_glossary_entry(conn, cur_term, lang="ko")
                        if entry:
                            glossary_map[cur_term] = {
                                "shortLabel": entry.short_label,
                                "explanation": entry.explanation,
                                "direction": entry.signal_direction,
                            }
                current_candidates.append((it, cs))

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

        # 경제 뉴스 15건: 국내 최대 10 + 해외 최대 5, 인터리브. 한쪽 부족하면 반대쪽이 메움
        from itertools import zip_longest

        dom_slice = stock_news_domestic[:10]
        for_slice = stock_news_foreign[:5]
        fresh_news: list[CollectedItem] = []
        for d, f in zip_longest(dom_slice, for_slice):
            if d is not None:
                fresh_news.append(d)
            if f is not None:
                fresh_news.append(f)
        # 15 미만이면 각 카테고리의 초과분으로 메움 (국내 우선)
        overflow = stock_news_domestic[10:] + stock_news_foreign[5:]
        fresh_news.extend(overflow[: max(0, 15 - len(fresh_news))])
        fresh_news = fresh_news[:15]
        # 경제 뉴스 + AI 국내 뉴스 요약 (배치)
        news_summaries: dict[str, str] = {}
        ai_title_translations: dict[str, str] = {}
        from news_briefing.collectors.rss import SOURCE_META as _AI_META

        # 영어로 발행되는 해외 RSS 소스 (번역 필요)
        _ENGLISH_SOURCES = {
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

        ai_items_limited = ai_news[:40]
        foreign_ai = [
            (it.ext_id, it.title, it.body or "")
            for it in ai_items_limited
            if _AI_META.get(it.source, ("foreign",))[0] == "foreign"
        ]
        domestic_ai = [
            (it.ext_id, it.title)
            for it in ai_items_limited
            if _AI_META.get(it.source, ("foreign",))[0] != "foreign"
        ]

        # fresh_news 중 영어 소스 → translate, 나머지 → summarize
        fresh_news_en = [it for it in fresh_news if it.source in _ENGLISH_SOURCES]
        fresh_news_ko = [it for it in fresh_news if it.source not in _ENGLISH_SOURCES]

        def _apply_translations(translations: dict[str, tuple[str, str]]) -> None:
            for ext_id, (title_ko, summary_ko) in translations.items():
                if title_ko:
                    ai_title_translations[ext_id] = title_ko
                if summary_ko:
                    news_summaries[ext_id] = summary_ko

        # 경제 뉴스(국문) + AI 국내 뉴스 요약 → 한 배치
        summarize_items = [(it.ext_id, it.title) for it in fresh_news_ko] + domestic_ai
        if summarize_items:
            with _timed(f"4. summarize_batch ({len(summarize_items)}건)"):
                summaries = summarize_batch(
                    conn,
                    summarize_items,
                    ollama_enabled=cfg.ollama_enabled,
                    ollama_model=cfg.ollama_model,
                )
            news_summaries.update(summaries)

        # 해외 영문 경제 뉴스 번역+요약
        if fresh_news_en:
            with _timed(f"4. translate_batch economy ({len(fresh_news_en)}건)"):
                _apply_translations(
                    translate_batch(
                        conn,
                        [(it.ext_id, it.title, it.body or "") for it in fresh_news_en],
                        ollama_enabled=cfg.ollama_enabled,
                        ollama_model=cfg.ollama_model,
                    )
                )

        # 해외 AI 뉴스 번역+요약
        if foreign_ai:
            with _timed(f"4. translate_batch AI ({len(foreign_ai)}건)"):
                _apply_translations(
                    translate_batch(
                        conn,
                        foreign_ai,
                        ollama_enabled=cfg.ollama_enabled,
                        ollama_model=cfg.ollama_model,
                    )
                )

        # 해외 영문 시사 뉴스 번역+요약 — 노출될 항목만 사전 선별해 번역
        # (json_builder 와 동일 기준으로 노출분만 추림. 전량 번역 → 노출분 번역 최적화:
        #  영문 시사 후보 수백 건 중 실제 노출은 섹션 cap 합 십여 건뿐이라 대부분이 낭비였다.)
        displayed_current_ids = {it.ext_id for it in select_displayed_current(current_candidates)}
        foreign_current_en = [
            (it.ext_id, it.title, it.body or "")
            for it, _ in current_candidates
            if it.source in _ENGLISH_SOURCES and it.ext_id in displayed_current_ids
        ]
        if foreign_current_en:
            with _timed(f"4. translate_batch current ({len(foreign_current_en)}건)"):
                _apply_translations(
                    translate_batch(
                        conn,
                        foreign_current_en,
                        ollama_enabled=cfg.ollama_enabled,
                        ollama_model=cfg.ollama_model,
                    )
                )

        # 5. 디지스트 텍스트 백업 (Week 1 그대로)
        with _timed("5. digest write"):
            text = format_digest(
                date=now, scored_signals=scored, news=fresh_news, min_score=MIN_SIGNAL_SCORE
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
        # 영어권 국제 시사 뉴스(BBC World 등)만 — 한국어 소스(연합뉴스 국제·gnews-intl-kr) 제외
        for it, _cs in current_candidates:
            if (it.extra or {}).get(
                "category"
            ) == "international" and it.source in _ENGLISH_SOURCES:
                foreign_candidates.append((it, foreign_news_weight(it.source)))

        domestic_candidates: list[tuple[CollectedItem, int]] = []
        for it, s, _d in scored:
            if it.source == "dart":
                domestic_candidates.append((it, s))
        for it, s, _d in research_scored:
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

        # 7b. Briefing JSON
        with _timed("7b. build+write briefing JSON"):
            briefing = build_briefing_json(
                date=now,
                scored_signals=scored,
                economy_news=fresh_news,
                current_news=current_candidates,
                ai_news=ai_news,
                glossary=glossary_map,
                term_ids_by_id=term_ids_by_id,
                hot_issues_foreign=hot_issues_foreign,
                hot_issues_domestic=hot_issues_domestic,
                news_summaries=news_summaries,
                ai_title_translations=ai_title_translations,
                macro_indices=macro_indices,
                research_scored=research_scored,
                etf_snapshots=etf_snapshots,
                phase_map=phase_map,
            )
            briefing_json_path = write_briefing(
                public_briefings_dir=cfg.public_briefings_dir, briefing=briefing
            )

        # 7c. Supabase briefings 테이블에 저장 (프론트엔드 직접 읽기)
        with _timed("7c. upsert Supabase briefing"):
            try:
                from news_briefing.storage.briefings import upsert_briefing

                upsert_briefing(conn, briefing["date"], briefing)
                log.info("briefing upserted to Supabase: %s", briefing["date"])
            except Exception as e:
                log.warning("briefing Supabase 저장 실패: %s", e)

        # 7d. picks 성과 히스토리 갱신
        with _timed("7d. picks history update"):
            try:
                from news_briefing.analysis.picks_tracker import (  # noqa: PLC0415
                    load_briefings_from_supabase,
                    update_history,
                )

                recent_briefings = load_briefings_from_supabase(limit=30)
                update_history(recent_briefings)
                log.info("picks_history.json 갱신 완료")
            except Exception as e:
                log.warning("picks 히스토리 갱신 실패: %s", e)

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
        if not dry_run:
            link_url = f"{cfg.vercel_base_url}/?date={now.strftime('%Y-%m-%d')}&tab=ai"
            message = (
                f"**데일리 브리핑 · {now.strftime('%m월 %d일')}**\n"
                f"AI {len(ai_news)}건 · 공시 {sig_above}건 · 뉴스 {len(fresh_news)}건\n"
                f"{link_url}"
            )
            sent = _send_discord(cfg, message)
        else:
            sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))

        # picks는 hot_issues 각 이슈의 picks 배열에 들어있으므로 종목 수를 합산한다.
        picks_domestic = sum(len(iss.get("picks") or []) for iss in hot_issues_domestic)
        picks_foreign = sum(len(iss.get("picks") or []) for iss in hot_issues_foreign)

        return MorningResult(
            new_items=len(new_items),
            signal_count=sig_above,
            news_count=len(fresh_news),
            current_count=len(current_candidates),
            ai_count=len(ai_news),
            picks_domestic=picks_domestic,
            picks_foreign=picks_foreign,
            digest_path=digest_path,
            briefing_json_path=briefing_json_path,
            sent_discord=sent,
        )
    finally:
        conn.close()
