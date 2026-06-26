"""엔트리 포인트 CLI.

사용법:
  python -m news_briefing morning [--dry-run] [--no-notify]
  python -m news_briefing status
  python -m news_briefing themes seed
  python -m news_briefing themes refresh <theme_id>
  python -m news_briefing weekly [--llm]
  python -m news_briefing screen [--dry-run] [--no-llm]
  python -m news_briefing ask "질의" [--top-k N]
  python -m news_briefing picks [--date YYYY-MM-DD] [--short]
  python -m news_briefing outcomes [--no-backfill] [--since YYYY-MM-DD]
  python -m news_briefing export-briefings [--days N]
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
    result = run_morning(cfg, dry_run=args.dry_run, notify=not args.no_notify)
    print(
        f"\n완료: 신규 {result.new_items}건, 공시 {result.signal_count}건, "
        f"추천 해외 {result.picks_foreign}/국내 {result.picks_domestic}종목, "
        f"전송={'OK' if result.sent_discord else 'SKIP'}"
    )
    print(f"백업: {result.digest_path}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config()
    print("뉴스 브리핑 상태")
    print(f"  Supabase: {cfg.supabase_url}")
    print(
        f"  Discord 웹훅: {'설정됨' if cfg.discord_webhook_url else '없음 (.env에 DISCORD_WEBHOOK_URL 추가 필요)'}"
    )
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
        print(f"seed 적용 완료: {len(result)} 테마, {sum(result.values())} 기업")
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
    print(f"  {report.week_id} · {len(report.top_signals)}개 시그널 · 트렌드 [{trending}]")
    if essay:
        print(f"  에세이 {len(essay)}자 포함")
    return 0


def _cmd_screen(args: argparse.Namespace) -> int:
    """펀더멘털 발굴 스크린 (온디맨드).

    이벤트 구동 picks 와 별개로 고정 유니버스를 정량 스캔해 저평가·우량·성장 종목을
    추린다. --no-llm 은 정량 숏리스트만, 기본은 LLM 심층 리서치까지.
    --dry-run 이 아니면 스냅샷을 Supabase(원본) + 로컬 JSON 에 저장해 앱에 노출한다.
    """
    from news_briefing.analysis.discovery import build_snapshot, deep_research, run_screen

    result = run_screen()

    def _print_quant(scope_name: str, rows: list) -> None:
        print(f"\n[{scope_name}] 발굴 숏리스트 {len(rows)}종목")
        for r in rows:
            tags = ("·".join(r.highlights)) if r.highlights else "—"
            v = r.value_score if r.value_score is not None else "—"
            q = r.quality_score if r.quality_score is not None else "—"
            g = r.growth_score if r.growth_score is not None else "—"
            print(
                f"  {r.composite:3}  {r.ticker:12} {(r.name or '')[:18]:18} V{v} Q{q} G{g}  {tags}"
            )

    if args.no_llm:
        _print_quant("US", result.us)
        _print_quant("KOSPI", result.kospi)
        print()
        return 0

    enriched = deep_research(result)
    for scope_name, scope_key in (("US", "us"), ("KOSPI", "kospi")):
        items = enriched.get(scope_key, [])
        print(f"\n[{scope_name}] 발굴 리서치 {len(items)}종목")
        for it in items:
            print(f"  {it['composite']:3}  {it['ticker']:12} {(it.get('name') or '')[:18]:18}")
            if it.get("thesis"):
                print(f"       논리: {it['thesis']}")
            if it.get("keyRisks"):
                print(f"       리스크: {it['keyRisks']}")
            etf = it.get("relatedEtf")
            if etf:
                print(f"       국내 ETF: {etf['name']} ({etf['ticker']})")

    snapshot = build_snapshot(enriched)
    if args.dry_run:
        print("\n[dry-run] 저장·배포 생략")
        return 0

    _persist_discovery(snapshot)
    print()
    return 0


def _persist_discovery(snapshot: dict) -> None:
    """발굴 스냅샷을 로컬 JSON + Supabase(원본)에 저장한다.

    로컬 파일은 항상 기록(생성 머신 미리보기), Supabase 는 실패해도 로컬은 남도록
    예외를 잡는다(테이블 미적용 등). DECISIONS #16 — Supabase 가 단일 원본.
    """
    from news_briefing.storage.discovery import upsert_discovery, write_discovery_local

    cfg = load_config()
    local_path = cfg.public_briefings_dir.parent / "discovery.json"
    write_discovery_local(local_path, snapshot)
    print(f"발굴 스냅샷 로컬 저장: {local_path}")

    try:
        from news_briefing.storage.db import get_client

        conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
        try:
            upsert_discovery(conn, snapshot)
            print("발굴 스냅샷 Supabase 저장 완료 (id=current)")
        finally:
            conn.close()
    except Exception as e:
        print(f"발굴 스냅샷 Supabase 저장 실패(로컬은 저장됨): {e}", file=sys.stderr)


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


def _cmd_export_briefings(args: argparse.Namespace) -> int:
    """Supabase에 보관된 과거 브리핑을 로컬 정적 파일로 복원한다.

    프론트엔드는 로컬 파일만 읽으므로, cleanup으로 지워진 달력의 과거 날짜를
    DB(원본)에서 다시 채울 때 쓴다. 외부 상태 변경 없음(읽기 + 로컬 쓰기).
    """
    from news_briefing.storage.briefings import export_briefings_to_local
    from news_briefing.storage.cleanup import BRIEFINGS_KEEP_DAYS
    from news_briefing.storage.db import get_client

    cfg = load_config()
    keep = args.days or BRIEFINGS_KEEP_DAYS
    conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
    try:
        dates = export_briefings_to_local(conn, cfg.public_briefings_dir, keep_days=keep)
    finally:
        conn.close()
    print(f"브리핑 {len(dates)}일치 로컬 복원 완료")
    if dates:
        print(f"  최신 {dates[0]} ~ 최古 {dates[-1]}")
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
                review = " ⚠️추가확인" if p.get("verifyStatus") == "review" else ""
                lines.append(f"  ● {ticker} {name}  [consensus_risk:{risk}]{review}")
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


def _cmd_outcomes(args: argparse.Namespace) -> int:
    """추천 픽 영구 원장을 채점하고 촉매별 적중률을 출력한다.

    --no-backfill 이면 채점은 건너뛰고 집계만 본다. 백필은 yfinance 읽기 +
    Supabase 쓰기(원장 갱신)뿐이며 외부 발송은 없다.
    """
    from news_briefing.analysis.picks_outcomes import (
        backfill_outcomes,
        calibration_report,
        format_report,
        seed_outcomes,
    )
    from news_briefing.storage.db import get_client

    cfg = load_config()
    conn = get_client(cfg.supabase_url, cfg.supabase_service_key)
    try:
        if args.seed:
            from news_briefing.analysis.picks_tracker import (
                load_briefings_from_local,
                load_briefings_from_supabase,
            )

            briefings = load_briefings_from_local() or load_briefings_from_supabase()
            seeded = seed_outcomes(conn, briefings)
            print(f"시드: {seeded}건 신규 스냅샷 ({len(briefings)}개 브리핑)\n")
        if not args.no_backfill:
            graded = backfill_outcomes(conn)
            print(f"채점 갱신: {graded}건\n")
        report = calibration_report(conn, since=args.since)
        text = format_report(report)
    finally:
        conn.close()
    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
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
    p_morning.add_argument("--dry-run", action="store_true", help="전송·배포 안 하고 stdout 으로만")
    p_morning.add_argument(
        "--no-notify",
        action="store_true",
        help="배포는 하되 Discord 알림은 건너뜀 (조용한 재배포)",
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

    p_screen = sub.add_parser("screen", help="펀더멘털 발굴 스크린 (저평가·우량·성장 종목)")
    p_screen.add_argument("--dry-run", action="store_true", help="저장·배포 없이 stdout 으로만")
    p_screen.add_argument("--no-llm", action="store_true", help="정량 숏리스트만(LLM 리서치 생략)")
    p_screen.set_defaults(func=_cmd_screen)

    sub.add_parser("cleanup", help="오래된 데이터 수동 정리").set_defaults(func=_cmd_cleanup)

    p_export = sub.add_parser(
        "export-briefings", help="Supabase 과거 브리핑을 로컬 파일로 복원 (달력 백필)"
    )
    p_export.add_argument("--days", type=int, default=None, help="복원할 최근 일수 (기본 30)")
    p_export.set_defaults(func=_cmd_export_briefings)

    p_outcomes = sub.add_parser("outcomes", help="추천 픽 원장 채점 + 촉매별 적중률 집계")
    p_outcomes.add_argument(
        "--seed", action="store_true", help="과거 브리핑 픽을 원장에 일괄 스냅샷(최초 1회)"
    )
    p_outcomes.add_argument("--no-backfill", action="store_true", help="채점 건너뛰고 집계만 출력")
    p_outcomes.add_argument("--since", help="집계 시작일 YYYY-MM-DD (기본: 전체)")
    p_outcomes.set_defaults(func=_cmd_outcomes)

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
