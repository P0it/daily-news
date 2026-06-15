"""엔트리 포인트 CLI.

사용법:
  python -m news_briefing morning [--dry-run]
  python -m news_briefing status
  python -m news_briefing themes seed
  python -m news_briefing themes refresh <theme_id>
  python -m news_briefing weekly [--llm]
  python -m news_briefing ask "질의" [--top-k N]
  python -m news_briefing picks [--date YYYY-MM-DD] [--short]
"""
from __future__ import annotations

import argparse
import logging
import sys

from news_briefing.config import PROJECT_ROOT, load_config
from news_briefing.orchestrator import run_morning


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def _cmd_morning(args: argparse.Namespace) -> int:
    cfg = load_config()
    result = run_morning(cfg, dry_run=args.dry_run)
    print(
        f"\n완료: 신규 {result.new_items}건, "
        f"AI {result.ai_count}, 시그널 {result.signal_count}, "
        f"뉴스 {result.news_count}, 시사 {result.current_count}, "
        f"Pick 국내 {result.picks_domestic}/해외 {result.picks_foreign}, "
        f"전송={'OK' if result.sent_discord else 'SKIP'}"
    )
    print(f"백업: {result.digest_path}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config()
    print("뉴스 브리핑 상태")
    print(f"  Supabase: {cfg.supabase_url}")
    print(f"  Discord 웹훅: {'설정됨' if cfg.discord_webhook_url else '없음 (.env에 DISCORD_WEBHOOK_URL 추가 필요)'}")
    print(f"  DART 키: {'설정됨' if cfg.dart_api_key else '없음'}")
    print(f"  EDGAR UA: {'설정됨' if cfg.edgar_user_agent else '없음'}")
    print(f"  Ollama: {'ON' if cfg.ollama_enabled else 'OFF'}")
    digests = sorted(cfg.digests_dir.glob("*.txt"), reverse=True)[:3]
    print("  최근 백업:")
    for p in digests:
        print(f"    {p.name}")
    return 0


def _cmd_themes(args: argparse.Namespace) -> int:
    from news_briefing.storage.db import get_client

    cfg = load_config()
    if args.subcmd == "seed":
        from news_briefing.storage.themes import load_seed

        seed_path = PROJECT_ROOT / "data" / "themes_seed.json"
        if not seed_path.exists():
            print(f"seed 파일 없음: {seed_path}", file=sys.stderr)
            return 1
        conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
        try:
            result = load_seed(conn, seed_path)
        finally:
            conn.close()
        print(
            f"seed 적용 완료: {len(result)} 테마, {sum(result.values())} 기업"
        )
        return 0
    if args.subcmd == "refresh":
        from news_briefing.analysis.themes import refresh_theme_layers
        from news_briefing.storage.themes import get_theme

        conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
        try:
            theme = get_theme(conn, args.theme_id)
            if theme is None:
                print(f"테마 없음: {args.theme_id}", file=sys.stderr)
                return 1
            n = refresh_theme_layers(conn, theme)
            print(f"{theme.name_ko}: {n}개 레이어 갱신")
        finally:
            conn.close()
        return 0
    print("themes 서브커맨드: seed | refresh <theme_id>", file=sys.stderr)
    return 2


def _cmd_weekly(args: argparse.Namespace) -> int:
    from news_briefing.delivery.weekly import (
        collect_weekly,
        generate_essay,
        write_weekly,
    )
    from news_briefing.storage.db import get_client
    from news_briefing.storage.themes import list_themes

    cfg = load_config()
    conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
    try:
        themes = list_themes(conn)
    finally:
        conn.close()
    theme_keywords = {t.theme_id: [t.name_ko] for t in themes}

    report = collect_weekly(cfg.public_briefings_dir, theme_keywords=theme_keywords)
    essay = generate_essay(report) if args.llm else None

    reports_dir = cfg.data_dir / "reports"
    path = write_weekly(reports_dir=reports_dir, report=report, essay=essay)
    print(f"주간 리포트 생성: {path}")
    trending = ", ".join(report.trending_themes) if report.trending_themes else "—"
    print(
        f"  {report.week_id} · {len(report.top_signals)}개 시그널 · "
        f"트렌드 [{trending}]"
    )
    if essay:
        print(f"  에세이 {len(essay)}자 포함")
    return 0


def _cmd_cleanup(args: argparse.Namespace) -> int:
    from news_briefing.storage.cleanup import run_cleanup
    from news_briefing.storage.db import get_client

    cfg = load_config()
    conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
    try:
        run_cleanup(conn, digests_dir=cfg.digests_dir, briefings_dir=cfg.public_briefings_dir)
    finally:
        conn.close()
    print("정리 완료 (로그 참조)")
    return 0


def _cmd_picks(args: argparse.Namespace) -> int:
    """오늘(또는 지정일) 브리핑 JSON 에서 추천 종목만 뽑아 출력한다.

    뉴스·시그널 없이 picks 만 빠르게 확인하기 위한 뷰. 외부 호출 없이
    이미 생성된 frontend/public/briefings/<date>.json 만 읽는다.
    """
    import json

    cfg = load_config()
    briefings_dir = cfg.public_briefings_dir
    if args.date:
        path = briefings_dir / f"{args.date}.json"
    else:
        candidates = sorted(briefings_dir.glob("20*.json"), reverse=True)
        if not candidates:
            print(f"브리핑 JSON 없음: {briefings_dir}", file=sys.stderr)
            return 1
        path = candidates[0]
    if not path.exists():
        print(f"브리핑 JSON 없음: {path}", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    hot_issues = (((data.get("tabs") or {}).get("economy") or {}).get("hotIssues")) or {}

    lines: list[str] = [f"추천 종목 · {data.get('date', path.stem)}", ""]
    total = 0
    labels = {"foreign": "해외", "domestic": "국내"}
    for side in ("foreign", "domestic"):
        issues = hot_issues.get(side) or []
        n_picks = sum(len(iss.get("picks") or []) for iss in issues)
        total += n_picks
        lines.append(f"━━ {labels[side]} ({n_picks}종목 / {len(issues)}이슈) ━━")
        if not issues:
            lines.append("  (없음)")
        for iss in issues:
            direction = iss.get("direction") or ""
            head = f"■ [{iss.get('rank', '')}] {iss.get('asset', '')}"
            if iss.get("signal"):
                head += f" — {iss['signal']}"
            if direction:
                head += f" ({direction})"
            lines.append("")
            lines.append(head)
            for p in iss.get("picks") or []:
                ticker = p.get("ticker") or ""
                name = p.get("name") or ""
                risk = p.get("consensus_risk") or ""
                lines.append(f"  ● {ticker} {name}  [consensus_risk:{risk}]")
                if not args.short:
                    if p.get("description"):
                        lines.append(f"    {p['description']}")
                    etf = p.get("related_etf")
                    if isinstance(etf, dict) and (etf.get("ticker") or etf.get("name")):
                        lines.append(
                            f"    관련 ETF: {etf.get('ticker', '')} "
                            f"{etf.get('name', '')} ({etf.get('confidence', '')})"
                        )
        lines.append("")
    lines.append(f"합계: {total}종목")

    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8", errors="replace"))
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    from news_briefing.analysis.rag import answer_query
    from news_briefing.storage.db import get_client

    cfg = load_config()
    conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
    try:
        result = answer_query(
            conn,
            args.query,
            embed_model=cfg.ollama_embed_model,
            top_k=args.top_k,
        )
    finally:
        conn.close()
    print()
    print(result.answer)
    print()
    print(f"출처 {len(result.sources)}건:")
    for s in result.sources:
        print(f"  - {s['doc_id']} (유사도 {s['score']:.3f})")
        meta_url = (s.get("metadata") or {}).get("url")
        if meta_url:
            print(f"    {meta_url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(prog="news_briefing", description="데일리 브리핑 CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_morning = sub.add_parser("morning", help="아침 브리핑 실행")
    p_morning.add_argument(
        "--dry-run", action="store_true", help="카톡 전송 안 하고 stdout 으로만"
    )
    p_morning.set_defaults(func=_cmd_morning)

    p_status = sub.add_parser("status", help="시스템 상태 출력")
    p_status.set_defaults(func=_cmd_status)

    p_themes = sub.add_parser("themes", help="테마·밸류체인 관리")
    themes_sub = p_themes.add_subparsers(dest="subcmd")
    themes_sub.add_parser("seed", help="data/themes_seed.json 로부터 DB 로드")
    p_refresh = themes_sub.add_parser("refresh", help="LLM 으로 테마 밸류체인 재생성")
    p_refresh.add_argument("theme_id")
    p_themes.set_defaults(func=_cmd_themes)

    p_weekly = sub.add_parser("weekly", help="주간 리포트 생성 (일요일 저녁)")
    p_weekly.add_argument(
        "--llm", action="store_true", help="LLM 에세이 포함 (느림, claude CLI 필요)"
    )
    p_weekly.set_defaults(func=_cmd_weekly)

    sub.add_parser("cleanup", help="오래된 데이터 수동 정리").set_defaults(func=_cmd_cleanup)

    p_ask = sub.add_parser("ask", help="RAG 자유 질의")
    p_ask.add_argument("query", help="질의 내용")
    p_ask.add_argument("--top-k", type=int, default=5, help="retrieval top-k")
    p_ask.set_defaults(func=_cmd_ask)

    p_picks = sub.add_parser("picks", help="추천 종목만 출력 (생성된 브리핑 JSON 읽기)")
    p_picks.add_argument("--date", help="조회할 날짜 YYYY-MM-DD (기본: 최신)")
    p_picks.add_argument("--short", action="store_true", help="종목명만 간단히")
    p_picks.set_defaults(func=_cmd_picks)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2

    try:
        return args.func(args)
    except RuntimeError as e:
        print(f"에러: {e}", file=sys.stderr)
        return 1
