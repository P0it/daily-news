"""아침 브리핑 파이프라인 전체 플로우."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from news_briefing.analysis.llm import summarize
from news_briefing.analysis.scoring import score_report
from news_briefing.collectors.base import CollectedItem
from news_briefing.collectors.dart import fetch_dart_list
from news_briefing.collectors.rss import fetch_all_rss
from news_briefing.config import Config
from news_briefing.delivery.digest import format_digest, write_digest
from news_briefing.delivery.kakao import (
    compose_text_template,
    load_tokens,
    refresh_access_token,
    save_tokens,
    send_text,
)
from news_briefing.storage.db import connect
from news_briefing.storage.seen import is_seen, mark_seen

log = logging.getLogger(__name__)

MIN_SIGNAL_SCORE = 60  # SIGNALS.md 2.2
KAKAO_FALLBACK_URL = "https://news-briefing.vercel.app/?tab=economy"  # Week 2 배포 후 유효


@dataclass(frozen=True, slots=True)
class MorningResult:
    new_items: int
    signal_count: int
    news_count: int
    digest_path: Path
    sent_kakao: bool


def _send_kakao(cfg: Config, text_title: str) -> bool:
    """내부 헬퍼. 테스트에서 mock patch 타겟."""
    tokens = load_tokens(cfg.tokens_path)
    if tokens is None:
        log.warning(
            ".kakao_tokens.json 없음, 카톡 전송 스킵. kakao_auth.py 먼저 실행하세요."
        )
        return False

    payload = compose_text_template(text_title, KAKAO_FALLBACK_URL, "열기")
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
        # 1. 수집
        date_key = now.strftime("%Y%m%d")
        disclosures = fetch_dart_list(cfg.dart_api_key, date_key)
        news = fetch_all_rss()
        all_items = disclosures + news

        # 2. 중복 제거
        new_items: list[CollectedItem] = []
        for item in all_items:
            if not is_seen(conn, item.source, item.ext_id):
                new_items.append(item)
                mark_seen(conn, item.source, item.ext_id)

        # 3. 점수
        scored = []
        for it in new_items:
            if it.kind == "disclosure":
                s, d = score_report(it.title)
                scored.append((it, s, d))

        # 4. 요약 (뉴스 중 상위 15건만, 비용 절약)
        fresh_news = [it for it in new_items if it.kind == "news"][:15]
        for it in fresh_news:
            _ = summarize(
                conn,
                it.title,
                ollama_enabled=cfg.ollama_enabled,
                ollama_model=cfg.ollama_model,
            )

        # 5. 디지스트 파일 작성 (항상)
        text = format_digest(
            date=now, scored_signals=scored, news=fresh_news, min_score=MIN_SIGNAL_SCORE
        )
        digest_path = write_digest(digests_dir=cfg.digests_dir, date=now, text=text)

        # 6. 카톡 전송 (dry-run 아닐 때)
        sent = False
        sig_above = sum(1 for _, s, _ in scored if s >= MIN_SIGNAL_SCORE)
        if not dry_run:
            title = (
                f"데일리 브리핑 · {now.strftime('%m월 %d일')}\n"
                f"공시 {sig_above}건 · 뉴스 {len(fresh_news)}건"
            )
            sent = _send_kakao(cfg, title)
        else:
            print(text)  # dry-run: stdout 에 전체 디지스트 출력

        return MorningResult(
            new_items=len(new_items),
            signal_count=sig_above,
            news_count=len(fresh_news),
            digest_path=digest_path,
            sent_kakao=sent,
        )
    finally:
        conn.close()
