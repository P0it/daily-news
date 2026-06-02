"""아침 브리핑 파이프라인 전체 플로우."""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from news_briefing.analysis.curation import curation_score
from news_briefing.analysis.glossary import detect_term, ensure_glossary_entry
from news_briefing.analysis.llm import summarize_batch, translate_batch
from news_briefing.analysis.scoring import score_consensus, score_edgar, score_report
from news_briefing.analysis.hot_issues import analyze_hot_issues, analyze_hot_issues_domestic
from news_briefing.collectors.base import CollectedItem
from news_briefing.collectors.dart import fetch_dart_list
from news_briefing.collectors.edgar import fetch_all_edgar
from news_briefing.collectors.krx_etf import ETFSnapshot, fetch_krx_etf
from news_briefing.collectors.macro import fetch_macro
from news_briefing.collectors.research import fetch_research_reports
from news_briefing.collectors.rss import fetch_all_rss
from news_briefing.config import Config
from news_briefing.delivery.digest import format_digest, write_digest
from news_briefing.delivery.json_builder import build_briefing_json, write_briefing
from news_briefing.delivery.discord import send_message as discord_send
from news_briefing.storage.db import get_client
from news_briefing.storage.seen import batch_filter_unseen, batch_mark_seen
from news_briefing.storage.tickers import TickerRow, upsert_ticker

log = logging.getLogger(__name__)

MIN_SIGNAL_SCORE = 60  # SIGNALS.md 2.2


@dataclass(frozen=True, slots=True)
class MorningResult:
    new_items: int
    signal_count: int
    news_count: int
    current_count: int  # 시사 뉴스 수집 건수 (Week 3)
    ai_count: int       # AI 뉴스 수집 건수 (Week 5b)
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
    log.info("morning start date=%s dry_run=%s", now.date(), dry_run)

    conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
    try:
        # 0. 오래된 데이터 정리 (일회성 데이터, 매일 실행)
        from news_briefing.storage.cleanup import run_cleanup

        run_cleanup(conn, digests_dir=cfg.digests_dir, briefings_dir=cfg.public_briefings_dir, today=now.date())

        # 1. 수집 (DART + RSS + EDGAR + 거시지표 + 리서치 + KRX ETF)
        date_key = now.strftime("%Y%m%d")
        disclosures = fetch_dart_list(cfg.dart_api_key, date_key)
        news = fetch_all_rss()
        edgar_items = fetch_all_edgar(cfg.edgar_user_agent) if cfg.edgar_user_agent else []
        macro_indices = fetch_macro()
        research_raw = fetch_research_reports()
        etf_snapshots: list[ETFSnapshot] = fetch_krx_etf()
        all_items = disclosures + news + edgar_items + research_raw

        # 2. 중복 제거 (배치 조회) + DART tickers 매핑 자동 수집
        unseen_pairs = set(batch_filter_unseen(conn, [(i.source, i.ext_id) for i in all_items]))
        new_items: list[CollectedItem] = [i for i in all_items if (i.source, i.ext_id) in unseen_pairs]
        batch_mark_seen(conn, list(unseen_pairs))

        # DART tickers 배치 upsert
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

            if it.source == "edgar":
                form_type = (it.extra or {}).get("form_type", "")
                items_str = (it.extra or {}).get("items", "")
                s, d = score_edgar(form_type=form_type, items=items_str)
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
            "rss:bbc-world", "rss:bbc-business", "rss:ft-markets", "rss:marketwatch",
            "rss:gnews-world-en", "rss:gnews-business-en", "rss:gnews-tech-en",
            "rss:gnews-us-stocks-en", "rss:gnews-us-markets-en",
        }

        ai_items_limited = ai_news[:40]
        foreign_ai = [(it.ext_id, it.title, it.body or "") for it in ai_items_limited
                      if _AI_META.get(it.source, ("foreign",))[0] == "foreign"]
        domestic_ai = [(it.ext_id, it.title) for it in ai_items_limited
                       if _AI_META.get(it.source, ("foreign",))[0] != "foreign"]

        # fresh_news 중 영어 소스 → translate, 나머지 → summarize
        fresh_news_en = [it for it in fresh_news if it.source in _ENGLISH_SOURCES]
        fresh_news_ko = [it for it in fresh_news if it.source not in _ENGLISH_SOURCES]

        # 경제 뉴스(국문) + AI 국내 뉴스 요약 → 한 배치
        summarize_items = [(it.ext_id, it.title) for it in fresh_news_ko] + domestic_ai
        if summarize_items:
            summaries = summarize_batch(
                conn, summarize_items,
                ollama_enabled=cfg.ollama_enabled,
                ollama_model=cfg.ollama_model,
            )
            news_summaries.update(summaries)

        def _apply_translations(translations: dict[str, tuple[str, str]]) -> None:
            for ext_id, (title_ko, summary_ko) in translations.items():
                if title_ko:
                    ai_title_translations[ext_id] = title_ko
                if summary_ko:
                    news_summaries[ext_id] = summary_ko

        # 해외 영문 경제 뉴스 번역+요약
        if fresh_news_en:
            _apply_translations(translate_batch(
                conn,
                [(it.ext_id, it.title, it.body or "") for it in fresh_news_en],
                ollama_enabled=cfg.ollama_enabled,
                ollama_model=cfg.ollama_model,
            ))

        # 해외 AI 뉴스 번역+요약
        if foreign_ai:
            _apply_translations(translate_batch(
                conn, foreign_ai,
                ollama_enabled=cfg.ollama_enabled,
                ollama_model=cfg.ollama_model,
            ))

        # 해외 영문 시사 뉴스(international/tech/politics) 번역+요약
        foreign_current_en = [
            (it.ext_id, it.title, it.body or "")
            for it, _ in current_candidates
            if it.source in _ENGLISH_SOURCES
        ]
        if foreign_current_en:
            _apply_translations(translate_batch(
                conn, foreign_current_en,
                ollama_enabled=cfg.ollama_enabled,
                ollama_model=cfg.ollama_model,
            ))

        # 5. 디지스트 텍스트 백업 (Week 1 그대로)
        text = format_digest(
            date=now, scored_signals=scored, news=fresh_news, min_score=MIN_SIGNAL_SCORE
        )
        digest_path = write_digest(digests_dir=cfg.digests_dir, date=now, text=text)

        # 6. 오늘의 핵심 이슈 선정 — 해외 (EDGAR·FT·BBC) + 국내 (DART·리서치·한경) 분리 실행 오늘의 핵심 이슈 선정 — 해외 (EDGAR·FT·BBC) + 국내 (DART·리서치·한경) 분리 실행
        hot_issues_foreign: list[dict] = []
        try:
            foreign_candidates: list[tuple[CollectedItem, int]] = []
            for it, s, _d in scored:
                if it.source == "edgar":
                    foreign_candidates.append((it, s))
            for it in stock_news_foreign:
                foreign_candidates.append((it, 50))
            for it, cs in current_candidates:
                if (it.extra or {}).get("category") == "international":
                    foreign_candidates.append((it, cs))
            hot_issues_foreign = analyze_hot_issues(foreign_candidates)
        except Exception as e:
            log.warning("hot_issues(foreign) 분석 실패: %s", e)

        hot_issues_domestic: list[dict] = []
        try:
            domestic_candidates: list[tuple[CollectedItem, int]] = []
            for it, s, _d in scored:
                if it.source == "dart":
                    domestic_candidates.append((it, s))
            for it, s, _d in research_scored:
                domestic_candidates.append((it, s))
            for it in stock_news_domestic:
                domestic_candidates.append((it, 40))
            hot_issues_domestic = analyze_hot_issues_domestic(domestic_candidates)
        except Exception as e:
            log.warning("hot_issues(domestic) 분석 실패: %s", e)

        # 7b. Briefing JSON
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
        )
        briefing_json_path = write_briefing(
            public_briefings_dir=cfg.public_briefings_dir, briefing=briefing
        )

        # 7c. Supabase briefings 테이블에 저장 (프론트엔드 직접 읽기)
        try:
            from news_briefing.storage.briefings import upsert_briefing

            upsert_briefing(conn, briefing["date"], briefing)
            log.info("briefing upserted to Supabase: %s", briefing["date"])
        except Exception as e:
            log.warning("briefing Supabase 저장 실패: %s", e)

        # 8. RAG 자동 인덱싱 (Week 4) — 실패해도 morning 전체 중단 X
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

        return MorningResult(
            new_items=len(new_items),
            signal_count=sig_above,
            news_count=len(fresh_news),
            current_count=len(current_candidates),
            ai_count=len(ai_news),
            picks_domestic=0,
            picks_foreign=0,
            digest_path=digest_path,
            briefing_json_path=briefing_json_path,
            sent_discord=sent,
        )
    finally:
        conn.close()
