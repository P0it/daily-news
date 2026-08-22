# 데일리 브리핑 자동화·데이터 밀도 개선 설계

- 작성일: 2026-08-22
- 상태: 승인됨 (구현 계획 대기)
- 배경: 이 시스템을 포트폴리오로 공개한다. 채용 담당자가 임의의 날에 방문해도
  매일 갱신되는 아카이브와 채워진 종목 데이터를 봐야 한다.

## 1. 문제 정의

포트폴리오 공개를 막는 결함 네 가지를 실측으로 확인했다.

### 1.1 LLM 실패가 그대로 배포된다

2026-08-21 실행 로그:

```
07:13:57 hot_issues(foreign) LLM 분석 실패: claude cli returncode=1 stderr=
07:14:29 hot_issues(domestic) LLM 분석 최종 실패: claude cli returncode=1 stderr=
07:29:27 LLM 호출 9건 중 실패 9건 (실패율 100%)
```

`frontend/public/briefings/2026-08-21.json` 의 `hotIssues` 는 국내·해외 모두 0건이다.
종목 섹션이 통째로 비어 있다.

실패율 추이가 악화되고 있다: 0% → 11%(07-29) → 22%(08-06) → 29%(08-17) → 100%(08-21).

원인은 코드 버그가 아니다. 동일한 방식(`stdin` 전달, 임시 디렉토리 `cwd`, `--model opus`)
으로 재현을 시도하면 `rc=0` 으로 정상 응답한다. 그 시점의 일시적 상태 —
사용량 한도 소진이 가장 유력하다.

**그런데 원인을 확정할 수 없다.** `llm.py` 의 예외 메시지가 `stderr` 만 담는데
정작 `stderr` 는 비어 있었다:

```python
raise RuntimeError(f"claude cli returncode={result.returncode} stderr={result.stderr[:500]}")
```

Claude CLI 는 사용량 한도 같은 오류를 `stdout` 으로 내보낸다. 한 달간 실패율이
0%에서 100%로 오르는 동안 원인을 한 번도 관측하지 못한 직접 원인이 이 한 줄이다.

### 1.2 국내 후보가 구조적으로 굶는다

`hot_issues.py` 의 국내 호출은 `score_floor=75` 를 **전 티어에 공통 적용**한다.
반면 `orchestrator.py` 는 국내 뉴스에 점수를 **40 으로 고정** 부여한다.

```python
# orchestrator.py
domestic_candidates.append((it, 40))          # 한경·매경·연합 전부 40점

# hot_issues.py
_build_pool(candidates, source_tier_domestic,
            tier1_cap=15, tier2_cap=8, tier3_cap=3, score_floor=75)
```

40 < 75 이므로 국내 뉴스는 티어와 무관하게 100% 탈락한다. 로그가 이를 증명한다.

| 날짜 | foreign | domestic |
|---|---|---|
| 08-03 | 21개 (T1=10 T2=8 T3=3) | 3개 (T1=3 **T2=0 T3=0**) |
| 08-13 | 21개 | 2개 (T1=2 **T2=0 T3=0**) |
| 08-21 | 21개 | 2개 (T1=2 **T2=0 T3=0**) |

관측 기간 전체에서 domestic Tier2·Tier3 가 0 이 아닌 날이 **단 하루도 없다**.
LLM 에게 후보 2건을 주고 Top 3 를 고르라고 요구하는 상태다.

해외는 `score_floor` 기본값 40 을 쓰고 `foreign_news_weight()` 로 소스 신뢰도를
점수화(Tier1=65, Tier2=50, 그 외 42)하기 때문에 21건이 들어간다. 국내에만
대응 함수가 없다.

> 주의: `refactor/picks-only-focus` 브랜치는 cap 을 `tier2_cap=12` 로 늘렸지만
> `score_floor=75` 는 그대로 두었다. 통과 항목이 0 이므로 cap 확대는 효과가 없다.

### 1.3 아카이브가 매일 삭제된다

main 의 `storage/cleanup.py:purge_files()` 는 오늘 날짜를 제외한 모든 브리핑 JSON 을
삭제하고 `index.json` 을 오늘 하루로 덮어쓴다. 현재 `frontend/public/briefings/` 에
파일이 `2026-08-21.json` 하나뿐인 이유이며, 8-21 실행이 8-17 을 지운 이유다.

실패한 날이 성공한 과거 데이터까지 지우므로 1.1 과 결합하면 최악이 된다 —
빈 종목 섹션을 가진 하루짜리 사이트.

`refactor/picks-only-focus` 브랜치에서 `BRIEFINGS_KEEP_DAYS = 30` 으로 이미
수정되어 있으나, **파이프라인은 main 에서 돌기 때문에 실제로는 계속 삭제되고 있다.**

### 1.4 실행 자체가 결번이 많다

Supabase `briefings` 테이블 기준으로 2026-06-01 ~ 08-21 사이 평일 약 60일 중
**22일이 결번**이다. 실행률 약 63%.

```
결번 평일: 06-03, 06-08, 06-11, 06-12, 06-24, 07-02, 07-03, 07-06, 07-07,
          07-13, 07-14, 07-15, 07-16, 07-17, 07-20, 07-21, 07-23, 07-24,
          08-10, 08-14, 08-19, 08-20
```

07-13 ~ 07-24 처럼 2주 가까이 연속으로 비는 구간이 있다. macOS launchd 라
맥북 전원·절전 상태에 종속되기 때문이다. "매일 갱신"을 내세우는 포트폴리오에
치명적이다.

### 1.5 원본 데이터는 살아 있다 (기회)

1.3 의 삭제는 로컬 정적 파일에 한정된다. `orchestrator.py` 는 매 실행
`upsert_briefing()` 으로 브리핑 JSON 원본을 Supabase `briefings` 테이블에
저장해 왔고, 현재 **39일치(2026-06-01 ~ 08-21)** 가 보존되어 있다.

`refactor/picks-only-focus` 브랜치의 `export_briefings_to_local()` 이 이를
로컬로 복원하는 경로를 이미 제공한다. 즉 아카이브를 오늘부터 새로 쌓을 필요가
없고, 병합 즉시 39일치를 복구할 수 있다.

## 2. 범위

포함:

- `refactor/picks-only-focus` → `main` 병합
- GitHub Actions 기반 스케줄 실행으로 이전
- 주말 간소판 모드 신설
- 브리핑 아카이브 보존 정책 변경 및 Supabase 원본으로부터의 복구
- LLM 실패 진단·방어 3단 강화
- 국내 후보 선별 하한 분리 및 국내 뉴스 가중치 도입

제외 (Non-goals):

- 카카오톡 발송 복구. 이미 죽은 코드이며 발송은 Discord 웹훅으로 이전 완료
  (§7 참조).
- 새 수집기 추가. 국내 후보 부족은 필터 문제이지 수집원 부족 문제가 아님.
- 자동 매매 연결 (`DECISIONS.md` #1 유지).

## 3. 선행 작업 — 브랜치 병합

`refactor/picks-only-focus` 는 main 보다 95개 파일 / +17,557 라인 앞서 있고
발굴(discovery)·급상승(surge)·스크리너·picks 성과 원장을 담고 있다. 마지막 커밋은
2026-07-27 이며 main 에는 그 이후 데이터 커밋 15개가 쌓였다. 포트폴리오에 보여줄
기능 대부분이 미배포 상태이므로 먼저 병합한다.

`git merge-tree` 로 확인한 충돌은 6건이다.

| 파일 | 해결 방침 |
|---|---|
| `frontend/tsconfig.tsbuildinfo` | 삭제 후 `.gitignore` 등록. 빌드 산출물이 추적되고 있음 |
| `frontend/public/briefings/index.json` | main 버전 유지. 파이프라인이 매 실행 재생성함 |
| `frontend/public/picks_history.json` | main 버전 유지. 동일 사유 |
| `scripts/com.user.news-briefing.morning.plist` | main 버전. PATH·caffeinate 수정본이 최신 |
| `src/news_briefing/orchestrator.py` | 수동 병합. 브랜치의 surge·discovery 연결과 main 의 LLM 실패 가드를 모두 보존 |
| `frontend/src/app/page.tsx` | 수동 병합. 브랜치의 신규 탭과 main 의 시사 뉴스 중복 제거를 모두 보존 |

완료 게이트: `ruff format` · `ruff check` · `pytest` 전체 통과.

## 4. 실행 인프라 — GitHub Actions

`.github/workflows/daily-briefing.yml` 을 신설한다.

```yaml
on:
  schedule:
    - cron: '0 22 * * 0-4'   # 월~금 07:00 KST — 풀 파이프라인
    - cron: '0 22 * * 5,6'   # 토·일 07:00 KST — 주말 간소판
  workflow_dispatch:          # 수동 실행 (데모·복구용)
```

UTC 22:00 은 KST 익일 07:00 이다. 일~목(0-4) 22:00 UTC 가 월~금 07:00 KST 에,
금·토(5,6) 22:00 UTC 가 토·일 07:00 KST 에 대응한다.

LLM 은 Max 플랜 할당량을 유지한다 (`CLAUDE.md` P2). `claude setup-token` 으로
발급한 장기 OAuth 토큰을 `CLAUDE_CODE_OAUTH_TOKEN` 시크릿에 넣고 러너에서
Claude Code CLI 를 그대로 실행한다. `ANTHROPIC_API_KEY` 는 설정하지 않는다 —
설정하면 Max 대신 API 과금으로 넘어간다.

필요한 시크릿: `CLAUDE_CODE_OAUTH_TOKEN`, `DART_API_KEY`, `SUPABASE_URL`,
`SUPABASE_SERVICE_KEY`, `DISCORD_WEBHOOK_URL`, `EDGAR_USER_AGENT`.

운영 파라미터:

- `timeout-minutes: 30`. 실측 실행 시간은 363~547초(6~9분)이므로 충분한 여유.
- `concurrency` 그룹으로 중복 실행 차단.
- 커밋·푸시는 기존 `delivery/publish.py` 를 그대로 사용하되 Actions 봇 자격으로
  동작시킨다. 푸시가 Vercel 재배포를 트리거하는 현재 구조를 바꾸지 않는다.

launchd plist 는 삭제하지 않고 로컬 수동 실행 경로로 남긴다.

## 5. 주말 간소판

`morning --weekend` 플래그를 추가한다. 주말은 증시가 열리지 않아 공시·시세가
없으므로 종목 분석은 무의미하지만, 달력이 비면 "매일 돌아간다"는 인상이 깨진다.
뉴스·시사만 갱신해 달력을 채운다.

갱신 대상:

- `tabs.current.{politics, society, international, tech}` — 시사
- `tabs.ai.{domestic, foreign}` — AI 뉴스
- `tabs.economy.news` — 경제 뉴스

건너뛰는 대상:

- `tabs.economy.signals` — DART·EDGAR 공시. 주말에 발생하지 않음
- `hotIssues` / picks — 종목 선정
- `tabs.economy.research`, `tabs.economy.etf` — 장 미개장
- `picks_history` 성과 갱신 — 시세 없음

브리핑 JSON 에 `"mode": "weekend"` 를 넣는다. 프론트엔드는 이 값을 보고 종목
섹션을 빈 배열로 렌더링하는 대신 안내 문구로 대체한다. 빈 배열을 그대로
그리면 실패한 날과 구분되지 않는다.

문구는 `docs/DESIGN.md` 의 대화체 원칙을 따른다 (예: "주말엔 장이 쉬어요").

## 6. 데이터 보존과 아카이브 복구

**보존 기간.** `BRIEFINGS_KEEP_DAYS` 를 90 으로 설정한다.

브랜치의 30일은 `picks_history` 의 `MAX_TRACK_DAYS=30` 에 맞춘 값이지만,
포트폴리오 관점에서 달력 한 달치는 축적 인상이 약하다. 브리핑 JSON 하나가
약 100KB 이므로 90일이면 9MB 수준 — 정적 배포에 부담 없다.

`picks_history` 의 30일 추적 기간은 그대로 둔다. 성과 추적과 아카이브 열람은
목적이 다르므로 두 값이 어긋나도 무방하며, 이 차이를 `cleanup.py` 주석에 남긴다.

`index.json` 은 남은 브리핑 날짜를 최신순으로 담는다 (브랜치 구현 유지).

**아카이브 복구.** 1.5 에서 확인한 Supabase 원본 39일치를
`export_briefings_to_local(conn, briefings_dir, keep_days=90)` 로 로컬에 복원한다.
사이트가 하루짜리에서 39일치로 즉시 채워진다. 이 함수는 브랜치에 이미 있으므로
새로 구현하지 않고 호출 지점만 만든다.

복구는 두 곳에서 일어난다.

1. **1회성 백필** — 병합 직후 수동 실행해 39일치를 커밋한다.
2. **매 실행** — `cleanup` 직후 `export_briefings_to_local` 을 호출해 DB 를
   기준으로 로컬을 맞춘다. 로컬 파일이 유실되어도 다음 실행에서 자동 복원된다.

순서가 중요하다. `cleanup` 이 90일 이전 파일을 지운 뒤 export 가 DB 에서 90일치를
내려받아 `index.json` 을 쓴다. 반대로 실행하면 cleanup 이 방금 복원한 파일을
지우고 `index.json` 을 덮어써 복구가 무효화된다.

결번(1.4)은 이 복구로도 메워지지 않는다. 애초에 실행되지 않아 DB 에도 없기
때문이다. 앞으로의 결번을 막는 것이 §4 의 역할이다.

## 7. 실패 방어

세 겹으로 구성한다.

**1단 — 진단 가능하게.** `_call_claude` 의 실패 예외 메시지에 `stdout` 을 포함한다.
1.1 에서 확인했듯 이것이 원인 관측 불가의 직접 원인이다.

```python
raise RuntimeError(
    f"claude cli returncode={result.returncode} "
    f"stderr={result.stderr[:500]} stdout={result.stdout[:500]}"
)
```

**2단 — 불완전 판정.** 기존 LLM 실패율 가드(`MAX_LLM_FAILURE_RATE = 0.5`)에 더해,
`hotIssues` 가 국내·해외 **둘 다 0건**이면 불완전으로 판정한다. 평일에만 적용하며
주말 간소판은 `hotIssues` 가 원래 없으므로 이 규칙에서 제외한다.

**3단 — 배포 중단.** 불완전 판정 시 그날 JSON 을 커밋·푸시하지 않는다. 사이트는
직전 브리핑을 유지한다. 방문자는 항상 내용이 채워진 페이지를 본다. 대신
달력에는 그날이 비게 되며, 이는 빈 종목 섹션을 보여주는 것보다 낫다는 판단이다.

Discord 웹훅으로 실패 사유를 발송한다.

카카오톡은 복구하지 않는다. `delivery/kakao.py` 는 `orchestrator.py` 가 import
하지 않고 `.env.example` 에 `KAKAO_*` 변수도 없는 죽은 코드다 (커밋 `dcca63d`
에서 Discord 로 이전). 카카오 OAuth 의 `refresh_token` 2개월 만료는 CI 에서
갱신이 까다로운 반면 Discord 웹훅 URL 은 만료가 없어 CI 에 적합하다.

PlayMCP 카카오 커넥터도 대안이 되지 않는다. claude.ai 계정에 붙은 대화형 인증
커넥터라 파이썬 프로세스에서 호출할 수 없고 헤드리스 실행에 붙지 않으며,
메시지 200자 제한에 링크 버튼도 없어 현재의 "제목 + 사이트 링크" 형식보다
동선이 나쁘다.

## 8. 국내 후보 굶주림 해결

해외 경로와 대칭이 되도록 두 곳을 고친다.

**티어별 하한 분리.** `_build_pool` 의 단일 `score_floor` 를 티어별로 나눈다.

```python
def _build_pool(
    candidates, tier_fn, *,
    tier1_cap=None, tier2_cap=8, tier3_cap=3,
    tier1_floor=40, tier23_floor=40,
): ...
```

기본값을 둘 다 40 으로 두므로 **해외 경로의 동작은 바뀌지 않는다**. 해외는 현재
`score_floor=40` 을 전 티어에 적용하고 있고, 새 기본값이 이와 동일하다.
기존 `score_floor` 인자를 참조하는 테스트는 없어 인자명 변경은 안전하다.

국내 호출은 Tier1 에만 촉매 하한을 걸고 Tier2·3 은 뉴스를 허용한다.

```python
_build_pool(candidates, source_tier_domestic,
            tier1_cap=20, tier2_cap=12, tier3_cap=3,
            tier1_floor=75, tier23_floor=40)
```

Tier1 하한 75 를 유지하는 이유는 `scoring.py` 의 점수 체계 때문이다. 분기보고서
45점, 반기보고서 50점, 사업보고서 55점은 비촉매 정기 공시이고, 단일판매·공급계약
75점, 자기주식취득 80점, 영업(잠정)실적 85점이 실제 촉매다. 하한을 통째로 40 으로
내리면 정기보고서 제출 시즌에 비촉매 공시 수십 건이 실제 촉매를 밀어낸다.

**국내 뉴스 가중치 도입.** `foreign_news_weight()` 와 대칭인 함수를 추가한다.

```python
def domestic_news_weight(source: str) -> int:
    """국내 뉴스 소스의 신뢰도 기반 기본 점수. foreign_news_weight 와 대칭."""
    return {1: 65, 2: 50}.get(source_tier_domestic(source), 42)
```

`orchestrator.py` 의 40 고정을 제거한다.

```python
domestic_candidates.append((it, domestic_news_weight(it.source)))
```

`_TIER_MAP_DOMESTIC` 기준으로 한경·매경·연합은 Tier2 → 50점, Google News 국내는
Tier3 → 42점을 받아 `tier23_floor=40` 을 통과한다.

예상 효과: 국내 후보 2건 → 15건 내외. 해외(21건)와 대등해진다.

## 9. 테스트

- `_build_pool` 티어별 하한 — Tier1 은 75 미만 배제, Tier2·3 은 40 이상 통과
- `domestic_news_weight` — 소스별 점수 매핑
- 국내 후보 구성 — 뉴스가 후보 풀에 실제로 진입하는지 (1.2 회귀 방지)
- 주말 모드 — 건너뛸 섹션이 실제로 건너뛰어지고 `mode` 필드가 기록되는지
- 불완전 판정 가드 — `hotIssues` 양쪽 0건일 때 publish 가 호출되지 않는지
- `cleanup` 90일 보존 — 경계 날짜 및 형식 불일치 파일 처리
- `cleanup` → `export_briefings_to_local` 호출 순서 — export 결과가 cleanup 에
  덮어써지지 않는지 (§6 의 순서 의존성 회귀 방지)

브랜치의 `tests/test_cleanup.py` 를 확장해 재사용한다.

LLM 실패 재현 테스트는 넣지 않는다. 비결정적이며 `CLAUDE.md` 의 LLM 테스트
방침(프롬프트 구조·후처리 검증만)에 어긋난다.

## 10. 문서 갱신

- `docs/DECISIONS.md` — GitHub Actions 이전, 주말 간소판, 국내 하한 분리 결정 기록
- `CLAUDE.md` — 실행 커맨드에 `--weekend` 추가, launchd 설명을 Actions 기준으로 갱신
- `docs/ARCHITECTURE.md` — 실행 경로를 launchd 단독에서 Actions + 로컬 수동으로 정정
