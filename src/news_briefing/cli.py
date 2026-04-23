"""엔트리 포인트 CLI.

사용법:
  python -m news_briefing morning [--dry-run]
  python -m news_briefing status
"""
from __future__ import annotations

import argparse
import logging
import sys

from news_briefing.config import load_config
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
    print(f"  Ollama: {'ON' if cfg.ollama_enabled else 'OFF'}")
    digests = sorted(cfg.digests_dir.glob("*.txt"), reverse=True)[:3]
    print("  최근 백업:")
    for p in digests:
        print(f"    {p.name}")
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

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2

    try:
        return args.func(args)
    except RuntimeError as e:
        print(f"에러: {e}", file=sys.stderr)
        return 1
