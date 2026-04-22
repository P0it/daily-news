# 4주 개발 로드맵

각 주차는 **실제로 동작하는 결과물**로 끝난다. 중간 상태에서 멈춰도 가치가 있도록 점진적 개선 구조를 택한다.

## 전체 일정

| 주차 | 테마 | 핵심 결과물 | Definition of Done |
|------|------|------------|---------------------|
| Week 1 | 수집·요약·전송 MVP | 매일 아침 카톡 브리핑 실행 | 카톡으로 DART 공시 + 뉴스 요약 수신 |
| Week 2a | PWA 기반 + 시사/경제 2탭 + 해설 | 설치 가능한 브리핑 앱 | 홈 화면 설치, 다크모드, 2탭, 용어 주석, 시그널 v2 |
| Week 2b | 종목 탭 (Today's Pick) + 차트·딥링크 | 종목 스캔 뷰 + SEC EDGAR | 3탭 전환, 국내/해외 그리드, TradingView 아코디언, 증권사 딥링크 |
| Week 3 | 시사 뉴스 수집 + 테마·밸류체인 | 시사 탭 채우기, 테마주 DB | 정치·사회·국제·IT 카드 표시, 최소 30개 테마 매핑 |
| Week 4 | RAG 분석 + 주간 리포트 고도화 | 질문응답형 분석 엔진 | 자유 질의 응답, 경제 탭 테마 배너, 주간 리포트 에세이 |

---

## Week 1: 수집·요약·전송 MVP

### 목표

DART 공시와 뉴스를 수집해서 LLM으로 요약하고 카카오톡으로 발송하는 end-to-end 파이프라인을 완성한다. 이 주차가 끝나면 매일 아침 카톡으로 브리핑이 오기 시작한다.

### 작업 항목

1. **프로젝트 구조 초기화**
   - `docs/ARCHITECTURE.md`의 디렉토리 구조대로 생성
   - `uv` 또는 `pip` + venv 로 의존성 관리
   - `.env.example`, `.gitignore` 작성

2. **DART 수집기**
   - `opendart.fss.or.kr/api/list.json` 폴링
   - 전체 시장 스캔 (특정 종목 필터 없음, 100개+ 자연스럽게 커버)
   - SQLite `seen` 테이블로 중복 제거

3. **RSS 수집기**
   - 한국경제, 매경 RSS 우선 연결
   - 해외는 BBC Business, FT Markets 시도 (죽어있으면 Week 2에 대체)

4. **LLM 요약 모듈**
   - Claude Code CLI subprocess wrapper
   - Ollama fallback
   - SQLite `llm_cache` 테이블로 중복 호출 방지

5. **시그널 스코어링 v1**
   - `SIGNALS.md`의 공시 유형별 가중치 리스트 기반
   - 키워드 매칭 수준 (고도화는 Week 2)

6. **카카오 OAuth & 전송**
   - `kakao_auth.py` 1회 실행 스크립트
   - `.kakao_tokens.json` 자동 저장
   - access_token 만료 시 refresh_token 자동 갱신

7. **메인 CLI**
   - `python -m news_briefing morning` — 아침 브리핑 1회
   - `python -m news_briefing morning --dry-run` — stdout 출력만

8. **launchd 등록**
   - `com.user.news-briefing.morning.plist` — 평일 06:00
   - macOS sleep 후 깨어나도 실행 보장 (cron 대비 장점)

### Definition of Done

- [ ] 수동으로 `python -m news_briefing morning --dry-run` 실행 시 터미널에 브리핑 출력
- [ ] `python -m news_briefing morning` 실행 시 실제 카톡 수신
- [ ] 같은 공시를 두 번 실행해도 두 번 알림이 오지 않음 (dedup 동작)
- [ ] launchd가 다음 날 자동 실행 성공
- [ ] `data/digests/YYYY-MM-DD.txt` 에 백업 파일 존재

### 의도적으로 Week 1에 하지 않는 것

- 웹 페이지 생성 (카톡 본문에 텍스트만)
- 용어 자동 해설
- 썸네일 이미지
- 시그널 점수 고도화

---

## Week 2a: PWA 기반 + 시사/경제 2탭 + 해설

### 목표

알림을 "이해 가능한" 형태로 업그레이드한다. 용어 자동 주석, 설치 가능한 PWA, 시그널 점수 고도화. **디자인 시스템 전면 적용, 다크 모드, 다국어 기본 지원.** 종목 탭은 Week 2b 로 분리.

### 작업 항목

1. **Next.js 15 static export + Tailwind 초기화** (F16, F25, F26)
   - `frontend/` 디렉토리에 Next.js 15 + TypeScript + Tailwind 프로젝트 부트스트랩
   - Pretendard Variable 폰트 (CDN)
   - Tailwind 설정: DESIGN.md 색상 토큰, 타입 스케일, radius, 폰트 패밀리
   - CSS variables: 라이트·다크 모두 정의 (`DESIGN.md` 8.3)
   - `prefers-reduced-motion` 글로벌 respect

2. **PWA manifest + service worker**
   - `public/manifest.json` — 이름·아이콘(192/512px)·theme_color·display: standalone
   - 커스텀 service worker: 앱 셸 cache-first, 브리핑 JSON network-first + cache fallback (`ARCHITECTURE.md` 6.5)
   - `InstallPrompt` 컴포넌트: `beforeinstallprompt` 이벤트 캐치 → 커스텀 배너
   - iOS Safari 대체 안내 텍스트

3. **Vercel 배포 파이프라인**
   - GitHub 저장소 연결 → `main` push 자동 배포
   - 빌드 명령: `next build && next export` (out/ 디렉토리)
   - 환경 변수 (없음 — 순수 정적)
   - HTTPS 확인 (PWA 필수)

4. **JSON export 파이프라인 (백엔드 → 프론트엔드)**
   - `src/news_briefing/delivery/json_builder.py` — briefing JSON 생성
   - 스키마: `ARCHITECTURE.md` 6.4 `Briefing` 인터페이스 준수 (단, Week 2a 는 `hero`, `tabs.current`, `tabs.economy` 만; `tabs.picks` 는 Week 2b)
   - `frontend/public/briefings/YYYY-MM-DD.json` 에 기록
   - `briefings/index.json` 에 날짜 목록 유지

5. **탭 네비게이션 UI (F24, 2탭 임시)**
   - Pill segmented 스타일 (`DESIGN.md` 5.9)
   - **Week 2a 는 2탭**: 시사 (default, 좌측) / 경제 (우측). Week 2b 에서 종목 탭 추가.
   - URL 쿼리 동기화 (`?tab=current|economy&scope=all|domestic|foreign`)
   - 국내/해외 필터 chip (text + underline, `DESIGN.md` 5.9.1)
   - 탭별 스크롤 위치 기억 (localStorage)
   - 카톡 딥링크는 `?tab=economy` 강제
   - 좌우 키보드 탭 전환

6. **공통 컴포넌트 구현**
   - `SignalCard`, `HeroCard`, `CurrentNewsCard`, `MarketIndices`, `GlossaryPopover`
   - `DESIGN.md` 5.1–5.10 기준. chrome 없음, dot + 레이블만, one focused action

7. **다크 모드**
   - `prefers-color-scheme` 자동 감지 + 수동 토글 (localStorage)
   - CSS variables 로 light/dark 전환
   - WCAG AA 대비 검증

8. **용어 주석 엔진 (Glossary Annotator)**
   - `glossary` 테이블 스키마 구현 (`ARCHITECTURE.md` 5.3)
   - 공시 유형별로 처음 등장할 때 LLM (claude CLI) 이 해설 생성 → DB 캐시
   - JSON export 에 `glossaryTermId` 연결
   - UI: inset 해설 박스 (히어로 카드는 기본 펼침, 일반 카드는 chip+탭 확장). 첫 방문 3건 자동 펼침. "알겠어요" localStorage. (`DESIGN.md` 5.7)
   - 해설 템플릿과 생성 프롬프트는 `SIGNALS.md` 3절

9. **시그널 스코어링 v2**
   - 키워드 매칭 + **정량 변수** 반영
     - 공시 금액 (자기주식 취득 10억 vs 1000억)
     - 지분율 변화 (0.1% vs 5%)
     - 거래 유형 (매수/매도 구분)
   - 구체적 규칙은 `SIGNALS.md` 2.3
   - Week 1 의 `score_report` 시그니처 유지, 내부만 개선

10. **다국어 지원 (i18n)**
    - `frontend/src/lib/i18n/ko.json`, `en.json` UI 사전
    - 언어 토글 버튼 (헤더 우측 `KO / EN`, localStorage 저장)
    - 영어 요약·주석 lazy 생성 (DB 캐시 키 `(content_hash, lang)`)

11. **카톡 메시지 포맷 변경**
    - Week 1: 본문에 모든 요약 나열
    - Week 2a: text 템플릿 "데일리 브리핑 · N월 N일\n공시 X건 · 시사 Y건" + "열기" 버튼 (Vercel URL, `?tab=economy` 강제). `DECISIONS.md` #10
    - 긴급 (점수 85+) 은 종목명 + 한 줄 + 공시 원문 버튼 (DART URL 직결)

### Definition of Done (Week 2a)

- [ ] `frontend/` 에서 `npm run dev` 실행 시 로컬 앱 로드됨 (Next.js 15 + Tailwind + 디자인 시스템 적용)
- [ ] Vercel 배포된 URL 접속 시 앱 로드 (데스크탑 Chrome/Safari, 모바일 iOS Safari/Android Chrome)
- [ ] **홈 화면 설치 가능**, 설치 후 전체화면 실행 (데스크탑·모바일)
- [ ] **오프라인 상태에서 마지막 브리핑 열람 가능**
- [ ] 다크/라이트 모드 시스템 자동 감지 + 수동 토글, WCAG AA 통과
- [ ] KO ↔ EN 토글 시 UI chrome 전환, 요약·주석 lazy 생성
- [ ] **2탭 (시사·경제) 전환 동작**, URL 쿼리 동기화
- [ ] 카톡 메시지에 용어 해설 연결 (앱에서 챕 → 해설 노출)
- [ ] 카톡 "열기" 클릭 시 경제 탭으로 직접 진입
- [ ] 시그널 점수가 금액·비율에 따라 차별화 (동일 유형도 규모 차등)
- [ ] 토스 디자인 원칙 5가지 준수 (`DESIGN.md` 1절): chrome 없이 타이포로 위계, 대화체, 숫자 크게, 카드당 action 1개, 여유 여백

### 의도적으로 Week 2a 에 하지 않는 것

- 종목 탭 (Today's Pick) — Week 2b
- SEC EDGAR 수집 — Week 2b
- TradingView 차트 임베드 — Week 2b
- 증권사 딥링크 — Week 2b
- 썸네일 OG 이미지 추출 — Week 3

---

## Week 2b: 종목 탭 (Today's Pick) + SEC EDGAR + 차트·딥링크

### 목표

Week 2a 기반 위에 **종목 탭 (Today's Pick, `DECISIONS.md` #12)** 를 추가한다. 국내(DART) + 해외(SEC EDGAR) 시그널 상위 종목을 그리드로 스캔하고, 카드 탭 시 TradingView 차트와 증권사 딥링크로 바로 실행 동선까지 연결한다.

### 작업 항목

1. **SEC EDGAR 수집기** (F4)
   - 8-K (주요 사건) + Form 4 (내부자 매매) RSS 피드
   - SEC Rate limit (10 req/s) 존중, User-Agent 필수
   - 정규화된 `CollectedItem` 으로 변환, `source="edgar"`, `scope="foreign"`
   - 아침 배치에 통합 (한국 06:00 = 전일 미국장 마감 반영)

2. **SEC EDGAR 스코어링**
   - Form 4 매수/매도 구분 → Week 1 scoring.py 확장
   - 8-K Item 번호별 기본 점수 (Item 1.01 계약, Item 2.01 인수 등)
   - `SIGNALS.md` 2.1 표 해외 대응 섹션 추가 필요

3. **DART `corp_code` ↔ 종목코드 매핑** (F18 지원)
   - DART 기업 개황 API 로 매핑 테이블 구축
   - `storage/tickers.py` + `tickers` 테이블 (corp_code, stock_code, corp_name)
   - 하루 1회 동기화 (morning 시작 시 lazy refresh)

4. **종목 탭 UI (F24 확장, 3탭)**
   - 탭 네비게이션을 2탭 → 3탭 확장: `[시사] [경제] [종목]`
   - URL 쿼리 `?tab=picks` 신규
   - 기본 진입 (PWA 아이콘): 시사 유지. 카톡 딥링크 타겟은 Week 2b 완료 후 `?tab=picks` 전환 검토

5. **종목 그리드 컴포넌트**
   - `PicksGrid` 컴포넌트 — 데스크탑 2×컬럼 (좌 국내 / 우 해외), 모바일 세로 스택
   - 각 컬럼 섹션 헤더: "국내" / "해외", 서브 "Today's Pick · N건"
   - 6건씩 2×3 또는 3×2 컴팩트 그리드
   - 데스크탑 컨테이너 max-width 720px (기본 560px 에서 확장, `DESIGN.md` 4.2 보충)
   - 빈 상태 카피: "오늘은 조용한 종목 라인업이에요"

6. **종목 컴팩트 카드**
   - 종목명 (title-md 18/700) + 회사 코드 · 한 줄 이벤트 (14/500) · 시간 + 점수 dot
   - border/shadow 없음, 배경 대비로 구분
   - 탭 시 아코디언 펼침 (차트 + 딥링크 3개 + 원문 링크)
   - `DESIGN.md` 5.13 로 spec 추가 필요

7. **TradingView 위젯 임베드** (F18)
   - Embed Widget (무료, key 불필요)
   - 한국: `KRX:{종목코드}`, 미국 NASDAQ/NYSE: `NASDAQ:{ticker}` / `NYSE:{ticker}`
   - 모바일 340×220, 데스크탑 500×300
   - 아코디언 펼침/접힘 상태 localStorage
   - `prefers-reduced-motion` 존중

8. **증권사 딥링크 생성기** (F19)
   - `src/news_briefing/delivery/deeplinks.py` — 종목코드 → 3개 URL 생성
   - 토스증권: `supertoss://stock/{code}`
   - 증권플러스: `koreainvestment://stock/{code}`
   - 네이버증권: `https://m.stock.naver.com/domestic/stock/{code}/total`
   - 해외 종목은 딥링크 미지원 (카드 우측 하단 "해외 종목" 라벨)

9. **Today's Pick 선별 로직**
   - `orchestrator.py` 에 종목 선별 단계 추가
   - 국내: DART 공시 중 점수 상위 6건 (company_code 중복 제거)
   - 해외: EDGAR 중 점수 상위 6건
   - 같은 종목 중복 공시는 최고 점수만 노출
   - `json_builder.py` 에서 `tabs.picks` 구조 채우기

10. **카톡 메시지 업데이트 (optional)**
    - 본문 건수 표시에 "종목 X건" 추가 검토
    - 카카오 딥링크 타겟을 `?tab=economy` → `?tab=picks` 로 전환할지 결정

### Definition of Done (Week 2b)

- [ ] 종목 탭 진입 시 국내/해외 2×컬럼 그리드 렌더, 모바일에서는 세로 스택
- [ ] 국내 카드 탭 시 TradingView 차트 (KRX:종목코드) 정상 렌더
- [ ] 해외 카드 탭 시 TradingView 차트 (NASDAQ:/NYSE:) 정상 렌더
- [ ] 국내 카드에 증권사 딥링크 3개 (토스·증권플러스·네이버) 버튼 노출, 각각 정상 앱 이동 (iOS/Android 각각 수동 검증)
- [ ] SEC EDGAR Form 4/8-K 가 해외 Today's Pick 에 포함됨
- [ ] 같은 종목이 여러 공시로 중복 노출되지 않음
- [ ] 탭 3개 (시사·경제·종목) 전환·URL 쿼리 동기화 동작
- [ ] `CLAUDE.md` P1 금칙어("추천") 가 UI·코드 어디에도 없음, "주목" / "Pick" 만 사용
- [ ] `DECISIONS.md` #12 재고 조건 2개가 README 또는 해당 문서에 명시돼 있음

### 의도적으로 Week 2b 에 하지 않는 것

- KIS API 실시간 시세 (F20) — Week 5+ 선택
- Today's Pick 과거 히스토리 페이지 (어제 Pick 이 뭐였는지)
- 종목 즐겨찾기·포트폴리오 관리
- 시사 뉴스 수집기 (F27-F30) — Week 3

---

## Week 3: 시사 뉴스 · 테마·밸류체인 · 차트

### 목표

단순 이벤트 알림에서 **테마 기반 분석**으로 확장하고, **시사 탭을 채운다**. 증권 탭에는 차트·딥링크를 얹어 실행 동선까지 완성.

### 작업 항목

1. **시사 뉴스 수집기 (F27~F30)**
   - 정치 RSS: 연합뉴스 정치, 한겨레 정치, 경향 정치
   - 사회 RSS: 연합뉴스 사회, 한겨레 사회
   - 국제 RSS: 연합뉴스 국제, BBC World, Reuters World
   - IT/과학 RSS: 디지털타임스, ZDNet Korea, 전자신문
   - 각 소스 응답 파싱, 중복 제거, SQLite 저장
   - 증권 수집기와 동일한 인프라 재사용 (`collectors/rss.py` 확장)

2. **시사 큐레이션 로직 (F31)**
   - 점수 공식: `소스 신뢰도 × 최신성 × LLM 중요도 판단`
   - 소스 신뢰도: 고정 값 (수동 튜닝)
   - 최신성: 최근 6시간 = 1.0, 12시간 = 0.5, 24시간 = 0.2
   - LLM 중요도: "오늘의 주요 국내 이슈인지 1~10점 평가" 프롬프트
   - 섹션별 top-N 선정 (정치 5, 사회 3, 국제 3, IT/과학 2)

3. **시사 용어 주석 (F32)**
   - 증권과 동일 메커니즘, 별도 `glossary` 레코드
   - 예: "전원합의체가 뭐예요?", "국정감사가 뭐예요?"

4. **차트 임베드 & 딥링크 (F18, F19)**
   - TradingView Embed Widget 통합 (카드 확장 시 아코디언)
   - DART `corp_code` ↔ 종목코드 매핑 테이블 구축
   - 딥링크 생성기: 토스증권 (`supertoss://stock/{code}`), 증권플러스, 네이버증권

5. **테마주 DB 구축**
   - 인포스탁(`infostock.co.kr`) 테마 페이지 크롤링
     - robots.txt 준수, 폴링 간격 5초+
     - 하루 1회 배치 업데이트
   - 한경 테마 페이지 교차 검증
   - `themes`, `value_layers`, `companies_in_layer` 테이블 채우기 (`ARCHITECTURE.md` 5.4)

6. **밸류체인 자동 분해**
   - 테마가 새로 감지되면 (뉴스 빈도 급증 기반) LLM에게:
     - "이 테마의 밸류체인 공통분모 섹터 3~5개를 한국 상장 관점에서 나열해줘"
   - 각 섹터와 기존 테마주 리스트를 매핑
   - 사람 검수 가능한 포맷으로 DB 저장 (`value_layers`)

7. **기업 포지셔닝 생성**
   - 각 상장사가 해당 레이어에서 어떤 포지션을 갖는지 LLM이 1~2줄 작성
   - 최근 공시·뉴스를 RAG 컨텍스트로 제공
   - 예: "에스피지: 하모닉 감속기 국내 3위, 2024년 로봇용 매출 40% 성장"

8. **트렌드 감지 로직**
   - RSS·공시에서 테마 키워드 등장 빈도 추적 (일간 대비 주간 이동평균)
   - 임계값 초과 시 "신규 주목 테마" 표시

9. **주간 리포트 템플릿**
   - 일요일 저녁 자동 생성 → 월요일 아침 카톡 링크
   - 이번 주 주목 테마 3개 + 각 테마의 밸류체인 시각화 + 상장사 리스트

### Definition of Done

- [ ] 시사 탭에 정치·사회·국제·IT 섹션이 채워짐, 섹션별 카드 표시
- [ ] 시사 기사 탭 시 용어 주석 팝오버 동작
- [ ] TradingView 차트가 경제 탭 카드에서 펼쳐짐
- [ ] 증권사 딥링크 3개 동작 확인 (iOS/Android 각각)
- [ ] `themes` 테이블에 최소 30개 테마, 각 테마당 5+ 기업 매핑
- [ ] 테마 쿼리 시 공통분모 섹터와 기업이 `positioning` 문장과 함께 반환됨
- [ ] 주간 리포트 HTML이 일요일 23:00에 자동 생성
- [ ] 트렌드 감지가 실제로 뜨는 테마를 포착하는지 수동 검증 (최소 2주 관찰)

---

## Week 4: RAG 분석

### 목표

수집한 모든 뉴스·공시·테마 DB를 **RAG 컨텍스트**로 묶어 자유 질의응답을 가능하게 한다. 주간 리포트 품질 향상.

### 작업 항목

1. **벡터 DB 구축**
   - 선택지: Chroma (로컬, 간단), LanceDB (임베디드, 성능), Qdrant (local docker)
   - 권장: Chroma (Week 4 스코프엔 충분)
   - 임베딩: OpenAI `text-embedding-3-small` 또는 로컬 `bge-m3`

2. **문서 인덱싱 파이프라인**
   - 매일 신규 뉴스·공시를 청킹해서 임베딩 → 벡터 DB
   - 메타데이터: 일자, 소스, 섹터, 관련 종목

3. **RAG 질의 엔진**
   - CLI 인터페이스 또는 웹 검색창
   - 쿼리 예: "최근 로봇 테마에서 자기주식 매수 공시 있었나?"
   - 프로세스:
     1. 쿼리 → 관련 문서 top-k 검색
     2. Claude에게 컨텍스트 + 쿼리 전달
     3. 출처 링크 포함 답변 생성

4. **테마 배너 UI (경제 탭 상단)**
   - 경제 탭 최상단에 "이번 주 주목 테마" 배너 추가
   - 배너 구조: 테마명 3개 + "자세히" 링크
   - 탭(click) 시 주간 리포트 페이지로 이동 (`/report/YYYY-Www`)
   - Week 3까지 테마 기능이 백엔드·DB 완성이었고, 이 주차에 UI 노출
   - 사용자에게는 "새 기능이 추가됐어요" 온보딩 토스트 1회 표시

5. **주간 리포트 고도화**
   - 단순 나열 → LLM이 "이번 주 핵심 흐름" 에세이형 요약 생성
   - 정량 데이터 (지수 변동, 외국인 수급) 자동 삽입
   - 지난주 리포트와 비교 섹션
   - 일요일 저녁 카톡에 **별도 URL 전송** (`https://.../report/2026-W17`)

6. **쿼리 히스토리 & 피드백**
   - 자주 묻는 질문 즐겨찾기
   - 답변에 "이 출처가 도움됐는가" 피드백 수집 → RAG 튜닝 힌트

### Definition of Done

- [ ] 자유 질의에 평균 10초 이내 응답 + 출처 링크 2개+
- [ ] 주간 리포트가 단순 나열이 아닌 해설·흐름 형태
- [ ] **경제 탭 상단 "이번 주 주목 테마" 배너 정상 노출, 주간 리포트 페이지로 이동**
- [ ] **일요일 23:00에 카톡으로 주간 리포트 URL 별도 전송**
- [ ] 지난 1개월 기사 대상 유의미한 RAG 검색 품질 (수동 평가 5문항 기준)

---

## 주차별 리스크와 완화책

| 리스크 | 해당 주차 | 완화책 |
|--------|-----------|---------|
| RSS 피드가 폐쇄됨 (FT, Reuters 등 일부) | Week 1 | 대체 피드 목록 준비, NewsAPI 유료 티어 검토 |
| Max 플랜 할당량 소진 | Week 2~4 | Ollama 자동 fallback, 배치 시간 분산 |
| 인포스탁 크롤링 차단 | Week 3 | 폴링 속도 낮춤 (하루 1회), 한경·네이버 테마 페이지로 대체 |
| 카톡 4KB 제한으로 내용 잘림 | Week 2 | 웹 링크 방식으로 해결 (Week 2에 진행) |
| launchd가 sleep 상태에서 못 깨움 | Week 1~2 | `pmset` 설정 조정, 실패 시 다음 주기에서 catch-up |
| 맥이 꺼진 기간 (해외 여행 등) | 상시 | 선택 작업 "여행 모드" 참고 (아래) |
| 테마 분석 LLM 할루시네이션 | Week 3~4 | 인포스탁 DB 교차검증, "확인 필요" 태그 |

## 선택 작업: 여행 모드 준비 (Week 2 이후 아무 때나)

맥 꺼진 기간 동안 GitHub Actions + Supabase + Anthropic API 키 조합으로 임시 전환 가능하게 하는 사전 준비. **해외 여행 예정이 있다면 출국 1~2주 전에 해두면 좋음.**

### 작업

1. **Anthropic API 키 발급**
   - https://console.anthropic.com 에서 API 키 생성
   - 월 $30 sp 지출 cap 설정 (안전장치)
   - 평소엔 미사용, 여행 시에만 활성화

2. **Supabase 프로젝트 생성 (무료 티어)**
   - `briefing` 프로젝트 생성, region `ap-northeast-2` (서울)
   - `seen`, `llm_cache`, `glossary` 테이블 SQLite 스키마와 동일하게 구성
   - `SUPABASE_URL` · `SUPABASE_SERVICE_KEY` 를 GitHub Secrets에 저장

3. **GitHub Actions workflow 파일**
   - `.github/workflows/morning.yml` 작성 (평소 disabled)
   - cron 트리거 `0 21 * * *` (KST 06:00 = UTC 21:00, 실제 도착은 06:15~06:40)
   - Secrets: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `KAKAO_ACCESS_TOKEN`, `KAKAO_REFRESH_TOKEN`, `VERCEL_TOKEN`
   - 실행 내용: checkout → Python setup → `pip install` → `python -m news_briefing morning --cloud`

4. **`--cloud` 플래그 분기 로직 (`cli.py`)**
   - 로컬: SQLite + Claude CLI
   - 클라우드: Supabase + Anthropic API
   - 환경 변수 `USE_ANTHROPIC_API=1` 또는 CLI 플래그로 분기

5. **DB 동기화 헬퍼**
   - `scripts/export-to-supabase.py` — 로컬 SQLite → Supabase
   - `scripts/import-from-supabase.py` — Supabase → 로컬 SQLite
   - 실행 시간 수 분 이내 (개인 사용 규모)

6. **여행 모드 체크리스트**
   - `scripts/travel-mode.md` 에 출국 전·귀국 후 순서 문서화
   - 출국 전: launchd unload → DB export → GitHub Actions enable
   - 귀국 후: GitHub Actions disable → DB import → launchd load

### Definition of Done

- [ ] GitHub Actions workflow `workflow_dispatch` 로 수동 실행 시 정상 동작
- [ ] Supabase에 하루 브리핑 결과가 저장됨
- [ ] Anthropic API 키 spend cap 설정 확인
- [ ] 체크리스트대로 모의 전환 (로컬 → 클라우드 → 로컬) 1회 성공

---

## 진행 원칙

1. **각 주차 DoD를 만족한 후에만 다음 주차 시작.** 미완료 상태로 다음 기능 쌓지 않는다
2. **매일 직접 써본다.** 시스템에 피드백 주면서 개선
3. **문서 업데이트는 코드 커밋과 함께.** `docs/` 변경 없이 기능 추가·변경 금지
4. **의도적 Non-goals 목록** (`PRD.md` 2.4) **은 절대 추가 금지.** 기능 욕심이 생기면 원칙 재확인
