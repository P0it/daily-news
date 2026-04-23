"""아침 브리핑 파이프라인 전체 플로우."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from news_briefing.analysis.curation import curation_score
from news_briefing.analysis.glossary import detect_term, ensure_glossary_entry
from news_briefing.analysis.llm import summarize
from news_briefing.analysis.picks import select_picks
from news_briefing.analysis.scoring import score_edgar, score_report
from news_briefing.analysis.trends import detect_trending_themes
from news_briefing.collectors.base import CollectedItem
from news_briefing.collectors.dart import fetch_dart_list
from news_briefing.collectors.edgar import fetch_all_edgar
from news_briefing.collectors.rss import fetch_all_rss
from news_briefing.config import Config
from news_briefing.delivery.digest import format_digest, write_digest
from news_briefing.delivery.json_builder import build_briefing_json, write_briefing
from news_briefing.delivery.kakao import (
    compose_text_template,
    load_tokens,
    refresh_access_token,
    save_tokens,
    send_text,
)
from news_briefing.storage.db import connect
from news_briefing.storage.seen import is_seen, mark_seen
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
    sent_kakao: bool


def _send_kakao(cfg: Config, text_title: str, link_url: str) -> bool:
    """내부 헬퍼. 테스트에서 mock patch 타겟."""
    tokens = load_tokens(cfg.tokens_path)
    if tokens is None:
        log.warning(
            ".kakao_tokens.json 없음, 카톡 전송 스킵. kakao_auth.py 먼저 실행하세요."
        )
        return False

    payload = compose_text_template(text_title, link_url, "열기")
    if send_text(tokens=tokens, rest_api_key=cfg.kakao_rest_api_key, payload=payload):
        return True

    # 401 의심 → refresh 시도
    refreshed = refresh_access_token(cfg.kakao_rest_api_key, tokens.refresh_token)
    if refreshed is None:
        log.error("refresh 실패. kakao_auth.py 재실행 필요.")
        return False
    save_tokens(cfg.tokens_path, refreshed)
    return send_text(
        tokens=refreshed, rest_api_key=cfg.kakao_rest_api_key, payload=payload
    )


def run_morning(
    cfg: Config, *, dry_run: bool = False, now: datetime | None = None
) -> MorningResult:
    now = now or datetime.now()
    log.info("morning start date=%s dry_run=%s", now.date(), dry_run)

    conn = connect(cfg.db_path)
    try:
        # 1. 수집 (DART + RSS + EDGAR)
        date_key = now.strftime("%Y%m%d")
        disclosures = fetch_dart_list(cfg.dart_api_key, date_key)
        news = fetch_all_rss()
        edgar_items = fetch_all_edgar(cfg.edgar_user_agent) if cfg.edgar_user_agent else []
        all_items = disclosures + news + edgar_items

        # 2. 중복 제거 + DART tickers 매핑 자동 수집
        new_items: list[CollectedItem] = []
        for item in all_items:
            if not is_seen(conn, item.source, item.ext_id):
                new_items.append(item)
                mark_seen(conn, item.source, item.ext_id)
                # DART stock_code + corp_code 가 있으면 tickers 테이블에 upsert
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
        # Week 5a (F36): 경제 뉴스 2줄 LLM 요약을 JSON 에 기록 → UI 표시
        news_summaries: dict[str, str] = {}
        for it in fresh_news:
            summary_text = summarize(
                conn,
                it.title,
                ollama_enabled=cfg.ollama_enabled,
                ollama_model=cfg.ollama_model,
            )
            if summary_text:
                news_summaries[it.ext_id] = summary_text

        # 5. 디지스트 텍스트 백업 (Week 1 그대로)
        text = format_digest(
            date=now, scored_signals=scored, news=fresh_news, min_score=MIN_SIGNAL_SCORE
        )
        digest_path = write_digest(digests_dir=cfg.digests_dir, date=now, text=text)

        # 6. Today's Pick 선별 (DECISIONS #12, Week 2b)
        picks = select_picks(scored, n_per_side=6)

        # 7a. Trending theme 감지 (Week 4 F12)
        theme_banner: dict | None = None
        try:
            from news_briefing.storage.themes import list_themes

            themes_list = list_themes(conn)
            theme_keywords = {t.theme_id: [t.name_ko] for t in themes_list}
            events = [(it.title, now) for it in new_items]
            trending_ids = (
                detect_trending_themes(
                    events, theme_keywords=theme_keywords, now=now
                )
                if theme_keywords
                else []
            )
            if trending_ids:
                name_by_id = {t.theme_id: t.name_ko for t in themes_list}
                week_id = f"{now.year}-W{now.isocalendar()[1]:02d}"
                theme_banner = {
                    "trendingThemes": [
                        name_by_id.get(tid, tid) for tid in trending_ids
                    ],
                    "reportUrl": f"/report/{week_id}",
                }
        except Exception as e:
            log.warning("trending theme 감지 실패: %s", e)

        # 7b. Briefing JSON
        briefing = build_briefing_json(
            date=now,
            scored_signals=scored,
            economy_news=fresh_news,
            current_news=current_candidates,
            ai_news=ai_news,
            glossary=glossary_map,
            term_ids_by_id=term_ids_by_id,
            picks=picks,
            theme_banner=theme_banner,
            news_summaries=news_summaries,
        )
        briefing_json_path = write_briefing(
            public_briefings_dir=cfg.public_briefings_dir, briefing=briefing
        )

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
            title = (
                f"데일리 브리핑 · {now.strftime('%m월 %d일')}\n"
                f"AI {len(ai_news)}건 · 공시 {sig_above}건 · 뉴스 {len(fresh_news)}건"
            )
            # Week 5b: 카톡 딥링크 default 를 AI 탭으로 (DECISIONS #13)
            link_url = (
                f"{cfg.vercel_base_url}/?date={now.strftime('%Y-%m-%d')}&tab=ai"
            )
            sent = _send_kakao(cfg, title, link_url)
        else:
            print(text)  # dry-run: stdout 에 전체 디지스트 출력

        return MorningResult(
            new_items=len(new_items),
            signal_count=sig_above,
            news_count=len(fresh_news),
            current_count=len(current_candidates),
            ai_count=len(ai_news),
            picks_domestic=len(picks.domestic),
            picks_foreign=len(picks.foreign),
            digest_path=digest_path,
            briefing_json_path=briefing_json_path,
            sent_kakao=sent,
        )
    finally:
        conn.close()
