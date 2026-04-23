"""엔트리 포인트 CLI.

사용법:
  python -m news_briefing morning [--dry-run]
  python -m news_briefing status
  python -m news_briefing themes seed
  python -m news_briefing themes refresh <theme_id>
  python -m news_briefing weekly [--llm]
  python -m news_briefing ask "질의" [--top-k N]
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
        f"\n완료: 신규 {result.new_items}건, 시그널 {result.signal_count}, "
        f"뉴스 {result.news_count}, 시사 {result.current_count}, "
        f"Pick 국내 {result.picks_domestic}/해외 {result.picks_foreign}, "
        f"전송={'OK' if result.sent_kakao else 'SKIP'}"
    )
    print(f"백업: {result.digest_path}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config()
    print("뉴스 브리핑 상태")
    print(f"  DB: {cfg.db_path} ({'있음' if cfg.db_path.exists() else '없음'})")
    tokens_state = (
        "있음" if cfg.tokens_path.exists() else "없음 (kakao_auth.py 실행 필요)"
    )
    print(f"  카카오 토큰: {cfg.tokens_path} ({tokens_state})")
    print(f"  DART 키: {'설정됨' if cfg.dart_api_key else '없음'}")
    print(f"  EDGAR UA: {'설정됨' if cfg.edgar_user_agent else '없음'}")
    print(f"  Ollama: {'ON' if cfg.ollama_enabled else 'OFF'}")
    digests = sorted(cfg.digests_dir.glob("*.txt"), reverse=True)[:3]
    print("  최근 백업:")
    for p in digests:
        print(f"    {p.name}")
    return 0


def _cmd_themes(args: argparse.Namespace) -> int:
    from news_briefing.storage.db import connect

    cfg = load_config()
    if args.subcmd == "seed":
        from news_briefing.storage.themes import load_seed

        seed_path = PROJECT_ROOT / "data" / "themes_seed.json"
        if not seed_path.exists():
            print(f"seed 파일 없음: {seed_path}", file=sys.stderr)
            return 1
        conn = connect(cfg.db_path)
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

        conn = connect(cfg.db_path)
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
    from news_briefing.delivery.weekly import collect_weekly, write_weekly

    cfg = load_config()
    reports_dir = cfg.data_dir / "reports"
    report = collect_weekly(cfg.public_briefings_dir)
    path = write_weekly(reports_dir=reports_dir, report=report)
    print(f"주간 리포트 생성: {path}")
    print(f"  {report.week_id} · {len(report.top_signals)}개 시그널")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    from news_briefing.analysis.rag import answer_query
    from news_briefing.storage.db import connect

    cfg = load_config()
    conn = connect(cfg.db_path)
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
    p_weekly.set_defaults(func=_cmd_weekly)

    p_ask = sub.add_parser("ask", help="RAG 자유 질의")
    p_ask.add_argument("query", help="질의 내용")
    p_ask.add_argument("--top-k", type=int, default=5, help="retrieval top-k")
    p_ask.set_defaults(func=_cmd_ask)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2

    try:
        return args.func(args)
    except RuntimeError as e:
        print(f"에러: {e}", file=sys.stderr)
        return 1
