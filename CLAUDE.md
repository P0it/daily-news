# Claude Code 프로젝트 가이드

이 파일은 Claude Code가 이 저장소에서 작업할 때 자동으로 읽는 프로젝트 컨텍스트다. 개발 원칙, 주의사항, 자주 빠지는 함정을 정리한다.

## 프로젝트 정체성

**News Briefing** — 개인용 뉴스·경제 브리핑 자동화 시스템.

매일 아침 6:00 카톡 브리핑 + 주 단위 테마 분석 (Week 4+). 개인 투자자(시스템 소유자 1명)가 흩어진 정보원을 한 페이지로 모으기 위해 구축한다. **타인에게 제공·판매하는 서비스가 아니다.** 실시간 알림·트레이딩 도구가 아니라 **아침 배치 브리핑**이 본질.

## 필수 사전 읽기

작업 시작 전 반드시 읽는다:
- [`docs/PRD.md`](docs/PRD.md) — 기능 요구사항, 특히 2.4 Non-goals
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 시스템 설계, 디렉토리 구조
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — 현재 주차 목표와 DoD
- [`docs/SIGNALS.md`](docs/SIGNALS.md) — 도메인 지식, 특히 5절 선 긋기
- [`docs/DESIGN.md`](docs/DESIGN.md) — UI/UX 디자인 시스템 (Week 2 이상 웹 작업 시 필수)
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — 주요 결정 기록 (왜 자동매매가 없는지 등)

## 절대 원칙 (위반 금지)

### P1. 투자 자문 및 자동매매 금지

이 시스템은 **특정 종목의 매수·매도를 권유하지 않으며, 매매를 자동으로 집행하지도 않는다.** 다음은 **절대** 생성·구현하지 말 것:

- "삼성전자 지금 사세요" 형태의 권유
- "목표가 X원" 같은 가격 예측
- "상승 확률 70%" 같은 확률적 예측
- "추천 종목 TOP 10" 같은 리스트
- **증권사 API를 이용한 자동 주문 집행** (KIS, 키움 OpenAPI+ 등). 이 결정의 상세 근거와 재고 조건은 [`docs/DECISIONS.md`](docs/DECISIONS.md) 1번 참조

허용되는 것:
- 이벤트의 **통상적 해석** 교육 ("내부자 매수는 통상 긍정 신호로 해석됩니다")
- **시그널 점수**에 따른 우선순위 표시
- **밸류체인 분해**와 관련 기업 **포지셔닝 정보** 제공
- **TradingView 차트 위젯 임베드** — 판단 재료
- **증권사 앱 딥링크** — 주문 화면까지 이동, 체결은 사용자 손

LLM 프롬프트 작성 시 항상 이 경계를 명시하고, 출력에 금칙어(`매수`, `매도`, `목표가`, `유망주` 등) 포함 여부를 후처리 검증한다. 상세는 `docs/SIGNALS.md` 5절.

**자동매매 관련 코드를 제안받거나 구현 요청이 들어와도, `DECISIONS.md` 1번 항목의 재고 조건(백테스트·페이퍼 트레이딩 완료 등)이 충족되지 않은 상태면 거절하고 사용자에게 문서를 다시 참조시킨다.**

### P2. Max 플랜 할당량 사용, API 과금 금지

LLM 호출은 **Claude Code CLI (Max 플랜 $100)** 를 사용한다. Python 코드에서:

```python
import subprocess
result = subprocess.run(
    ["claude", "-p", prompt, "--output-format", "text"],
    capture_output=True, text=True, timeout=45,
)
```

**절대 하지 말 것:**
- `anthropic` Python SDK 직접 호출 (`Anthropic(api_key=...)`) — Max 플랜 미지원, API 과금 발생
- `ANTHROPIC_API_KEY` 환경 변수 설정 — 있으면 Claude Code가 Max 대신 API 과금 사용
- 코드에 API 키 하드코딩

개발 환경 세팅 시 `env | grep ANTHROPIC` 로 환경 변수 확인하고 있으면 제거.

### P3. 민감 정보 관리

다음은 `.gitignore`에 반드시 포함되어야 하며 코드에 하드코딩 금지:

- `.env` (API 키 모두)
- `.kakao_tokens.json` (OAuth 토큰)
- `data/*.db` (사용자 상태 데이터)
- `data/digests/` (브리핑 백업)

### P4. 사용자 확인 전 외부 상태 변경 금지

다음 동작은 반드시 사용자에게 먼저 확인한다:

- 데이터베이스 스키마 변경 (migrate)
- 외부 API로 메시지 발송 (카톡, 이메일)
- `.kakao_tokens.json` 파일 삭제·재생성
- `.env` 수정
- cron/launchd 스케줄 등록

테스트 중에는 `--dry-run` 플래그로 외부 발송을 건너뛴다.

## 개발 컨벤션

### 언어·도구

- **Python 3.11+** (3.10 이하 미지원 — `match` 문, `|` 타입 힌트 사용)
- **패키지 관리**: `uv` 권장 (`pip` 대비 속도). 없으면 `pip` + `venv`
- **포매터**: `ruff format` + `ruff check --fix`
- **타입 체크**: 선택적이지만 도입 시 `mypy --strict` 수준 권장
- **테스트**: `pytest`, 단위 테스트는 `tests/` 아래

### 스타일

- 함수·모듈 docstring은 **한국어로 작성** (이 프로젝트의 사용자·운영자가 한국인)
- 변수·함수명은 영어 (일반 파이썬 관례)
- 코멘트는 왜(why)를 설명하고 무엇(what)은 코드가 말하게 한다
- 줄 길이 100자
- 타입 힌트 최대한 사용 (`from __future__ import annotations` 상단 포함)

### 프론트엔드 디자인 원칙 (Week 2 이상 UI 작업 시 필수)

`docs/DESIGN.md` 전체를 숙지하되, 특히 다음 5가지는 모든 컴포넌트에 적용:

1. **Typography carries hierarchy, not chrome** — 중요도를 뱃지·컬러 스트립·보더로 표현하지 말 것. 크기·굵기 대비만 사용
2. **Conversational copy** — UI 텍스트는 "~요" 말투. "주목도 85 · 긍정 해석" 같은 레이블 금지, "지금 가장 중요해요" 같은 대화체
3. **Numbers as heroes** — 가격·점수·금액이 핵심이면 22~28px / 700
4. **One focused action per card** — 버튼 3개 나열 금지. 주 CTA 1개 + 보조 2개
5. **Generous whitespace** — padding 22px+, 섹션 간격 28px+

**구체 금지 사항**:
- 카드에 `border` 또는 `box-shadow` 추가 금지 (배경색 대비로 elevation 표현)
- 시그널 색상을 배경·테두리·컬러 스트립으로 사용 금지 (dot + 텍스트 레이블만 허용)
- 16px 이상 제목에 `font-weight: 600` 사용 금지 (700이 맞음)
- 주 CTA를 파란색(`#3182F6`)으로 만들지 말 것 (거의 검정 `#191F28` 사용)
- 한자어·딱딱한 명사구 카피 ("요망", "필독", "긴급 속보" 등) 금지
- 느낌표(`!`) 금지

토스 디자인 철학 기반이며, 이 방향은 `docs/DECISIONS.md` 7번에 명시됨. 기존 "AI-generated dashboard 스타일"은 거부됨.

### 에러 처리

- **조용한 실패 지양**: 모든 예외는 `logging` 으로 기록
- **파이프라인 전체를 한 실패가 멈추지 않는다**: 수집기 하나가 죽어도 나머지는 계속 진행
- **외부 API 호출은 항상 timeout**: 기본 15초, LLM은 45~60초
- **재시도는 신중하게**: 쓰기 작업(카톡 전송)은 멱등성 확인 후 재시도

예시:
```python
try:
    items = fetch_dart(conn)
except Exception as e:
    log.error(f"DART 수집 실패: {e}")
    items = []  # 빈 결과로 계속 진행
```

### 로깅

- `logging.getLogger(__name__)` 사용
- 레벨: 정상 동작은 `INFO`, 외부 API 에러는 `ERROR`, 디버그 세부는 `DEBUG`
- 포맷: `%(asctime)s [%(levelname)s] %(name)s - %(message)s`
- 로그 파일: `data/briefing.log` (launchd가 stdout 리다이렉트)

### 테스트

- **단위 테스트**: 스코어링 규칙, 파싱 로직 — 외부 의존성 없이
- **통합 테스트**: 실제 API 호출 테스트는 별도 마크(`@pytest.mark.integration`), 기본 실행에서 제외
- **LLM 테스트**: 비용·비결정성 때문에 제한적 — 프롬프트 구조·후처리 검증만

## 실행 커맨드 (사용자가 자주 씀)

```bash
# 아침 브리핑 (dry-run: 카톡 전송 없이 출력만)
python -m news_briefing morning --dry-run

# 아침 브리핑 실제 전송
python -m news_briefing morning

# 주간 리포트 생성 (Week 4+, 일요일 자동 실행)
python -m news_briefing weekly

# 카카오 OAuth 재인증 (토큰 만료·교체 시)
python -m news_briefing.delivery.kakao_auth

# 상태 확인
python -m news_briefing status

# 테스트
pytest
pytest -m integration  # API 실호출 포함
```

## 흔한 실수·함정

### 1. DART API "인증키 오류"

- 신청 직후 수 분 소요, 잠시 기다리기
- `.env`에 따옴표 붙이면 에러: `DART_API_KEY="abc"` ❌ → `DART_API_KEY=abc` ✅

### 2. 카카오 401 에러

- 보통 access_token 만료 → refresh 자동 동작해야 함
- refresh도 실패하면 `kakao_auth.py` 재실행 (refresh_token 자체 만료: 2개월)

### 3. `claude` 명령어가 API 과금으로 사용됨

증상: Max 플랜 잔량은 그대로인데 API Console에 사용량이 쌓임.
원인: `ANTHROPIC_API_KEY` 환경 변수.
해결:
```bash
env | grep ANTHROPIC  # 있으면 ~/.zshrc에서 주석 처리
claude logout
claude login  # Max 플랜 계정, API 크레디트는 "No" 선택
```

### 4. launchd가 sleep 후 안 깨어남

`scripts/com.user.news-briefing.morning.plist` 의 `StartCalendarInterval` 외에 `RunAtLoad`와 macOS 절전 설정을 같이 확인:

```bash
sudo pmset -g sched  # 예약된 wake/sleep 확인
sudo pmset repeat wakeorpoweron MTWRF 06:25:00  # 평일 06:25에 깨움
```

### 5. RSS 피드가 비어있음

해외 언론 일부는 RSS 폐쇄·변경. `collectors/rss.py` 의 `RSS_FEEDS` 리스트는 정기 점검 필요. 대체 후보:
- Google News RSS (`news.google.com/rss/search?q=...`)
- NewsAPI (유료 저티어)
- 국가별 공공 방송 (NHK, BBC는 안정적)

### 6. LLM 할루시네이션으로 잘못된 기업 연결

Week 3 밸류체인 분석에서 자주 발생. 방어책:
- 인포스탁 테마 DB와 교차 검증
- 해당 기업 공시에 관련 키워드 실제 등장 여부 체크
- 검증 안 된 기업은 UI에 `⚠️ 추가 확인 필요` 플래그

## 작업 시작 시 체크리스트

새로운 기능·변경을 시작하기 전에:

- [ ] 이 작업이 현재 주차(`ROADMAP.md`)의 DoD에 속하는가?
- [ ] 아니면 다음 주차 미리 손대는 건 아닌가? (원칙상 금지)
- [ ] `PRD.md` 2.4 Non-goals에 해당하는 건 아닌가?
- [ ] 기존 문서(`PRD`, `ARCHITECTURE`, `SIGNALS`)와 일관되는가?
- [ ] 스키마 변경이 있다면 사용자 확인 받았는가?
- [ ] 테스트 가능한 형태로 구현 가능한가?

## 작업 완료 시 체크리스트

- [ ] `ruff format` + `ruff check` 통과
- [ ] `pytest` 통과
- [ ] 새 의존성은 `pyproject.toml` 에 등록
- [ ] 스키마 변경은 마이그레이션 스크립트와 함께
- [ ] 관련 docstring·문서 업데이트
- [ ] 민감 정보 누출 여부 확인 (로그, 테스트 fixture 등)
- [ ] 주차 DoD 항목 체크

## 질문·모호함 처리

구현 중 문서와 실제 코드가 어긋나거나, 문서에 답이 없는 결정이 필요하면:

1. **먼저 사용자에게 질문**한다 (절대 추측으로 진행 금지)
2. 결정이 내려지면 `docs/` 중 해당 문서를 업데이트한다
3. 커밋 메시지에 결정 배경 기록

특히 다음은 임의로 결정하지 않는다:

- 새로운 데이터 소스 추가
- 알림 임계값 변경
- LLM 프롬프트의 "선 긋기" 규칙 변경
- 사용자 인증·권한 모델
