# 시스템 아키텍처

## 1. 고수준 구조

시스템은 **백엔드 (데이터 파이프라인)** 와 **프론트엔드 (PWA 앱 셸)** 두 축으로 구성된다. 둘은 JSON 데이터 파일로 느슨하게 결합된다.

```mermaid
flowchart LR
    subgraph Backend[Backend · Python · 매일 06:00 배치]
        A[수집<br/>Collectors] --> B[정규화·저장<br/>Storage]
        B --> C[분석·가공<br/>Analysis]
        C --> D[데이터 생성<br/>JSON + Kakao]
    end
    
    subgraph Frontend[Frontend · PWA · 사용자 디바이스]
        E[App Shell<br/>index.html + JS]
        F[Service Worker<br/>오프라인 캐시]
        G[Manifest<br/>설치 지원]
    end
    
    D -- briefings/YYYY-MM-DD.json --> E
    E <--> F
    G --> E

    A1[DART Open API] --> A
    A2[증권 뉴스 RSS] --> A
    A3[시사 뉴스 RSS] --> A
    A4[SEC EDGAR] --> A
    A5[인포스탁 테마주] --> A
```

### 1.1 레이어 책임

| 레이어 | 책임 | 주요 컴포넌트 |
|--------|------|--------------|
| Collectors | 외부 소스에서 원시 데이터 수집, 정규화된 형태로 저장. 증권/시사 구분 | `collectors/dart.py`, `collectors/rss_stock.py`, `collectors/rss_current.py`, `collectors/edgar.py` |
| Storage | 중복 제거, 요약·주석 캐시, 영속 상태 관리 | SQLite (`briefing.db`) |
| Analysis | LLM 기반 요약·주석, 시그널 스코어링, 테마 분석, 시사 큐레이션 | `analysis/llm.py`, `analysis/scoring.py`, `analysis/glossary.py`, `analysis/curation.py`, `analysis/valuechain.py` |
| Delivery (백엔드) | JSON 데이터 파일 생성, 카카오톡 메시지 발송 | `delivery/json_builder.py`, `delivery/kakao.py` |
| Frontend (PWA) | 앱 셸, 데이터 렌더링, 오프라인·설치 지원 | Next.js 15 static export + React + Tailwind, `frontend/` 디렉토리 |

## 2. 데이터 흐름

### 2.1 아침 브리핑 (하루 1회, 06:00)

```mermaid
sequenceDiagram
    participant Cron
    participant Briefing as briefing.py (morning)
    participant DART
    participant RSS
    participant DB as SQLite
    participant LLM
    participant Web
    participant Kakao

    Cron->>Briefing: 06:00 트리거
    Briefing->>DART: 오늘 공시 전체 조회
    DART-->>Briefing: 공시 목록
    Briefing->>RSS: 뉴스 피드 조회
    RSS-->>Briefing: 기사 목록
    Briefing->>DB: 중복 체크 & 저장
    Briefing->>LLM: 각 항목 2줄 요약 (캐시 히트 시 스킵)
    LLM-->>Briefing: 요약 텍스트
    Briefing->>Briefing: 시그널 점수 산정
    Briefing->>Web: 반응형 HTML 생성 (Week 2+)
    Web-->>Briefing: 정적 페이지 URL
    Briefing->>Kakao: 헤드라인 + 웹 링크
    Kakao-->>Briefing: 전송 완료
```

### 2.2 주간 리포트 생성 (일요일 23:00)

```mermaid
sequenceDiagram
    participant launchd as launchd (weekly)
    participant Main as briefing.py (weekly)
    participant DB as SQLite
    participant LLM
    participant Vercel
    participant Kakao

    launchd->>Main: 일요일 23:00 기동
    Main->>DB: 지난 주(월~일) 시그널·뉴스 조회
    Main->>Main: 트렌드 감지 (키워드 빈도 이동평균)
    Main->>LLM: 주간 요약 에세이 생성 (Week 4+)
    LLM-->>Main: 리포트 텍스트
    Main->>Vercel: /report/YYYY-Www.json push
    Main->>Kakao: 리포트 링크 전송
```

**실시간 장중 폴링은 구현하지 않는다.** `PRD.md` 2.5 Non-goals 참조. 이 프로덕트는 아침 배치 브리핑 + 주간 리포트에 집중한다.

## 3. 기술 스택과 선택 이유

### 3.1 언어·프레임워크

| 영역 | 선택 | 이유 |
|------|------|------|
| 백엔드 | Python 3.11+ | DART/카카오 API, feedparser, 금융 라이브러리 생태계 풍부 |
| 프론트엔드 | PWA (HTML/CSS/JS + manifest + service worker) | 데스크탑·모바일 단일 코드, 설치·오프라인 지원. 네이티브 앱 불필요 |
| 프론트엔드 빌드 | Next.js 14 + `next-pwa` **또는** 정적 HTML + Tailwind CDN + vanilla SW | Week 2 착수 시 복잡도 판단. 정적 HTML이 기본, 기능 확장되면 Next.js 전환 |
| 호스팅 | Vercel 무료 티어 | 자동 HTTPS (PWA 필수), GitHub push 자동 배포, 커스텀 도메인 무료 |
| 스케줄러 | macOS launchd | cron 대비 sleep 복구에 안정적 |
| DB | SQLite | 로컬 단일 사용자, 백업·이식 간단 |

### 3.2 LLM 전략

**주 엔진: Claude Code CLI (Max 플랜 호출)**

- Max $100 플랜 할당량을 그대로 사용 (API 별도 과금 없음)
- Python에서 `subprocess.run(["claude", "-p", prompt, "--output-format", "json"])` 로 호출
- `ANTHROPIC_API_KEY` 환경 변수가 설정돼 있으면 구독 대신 API 과금 발생 → 반드시 제거
- 단점: Anthropic 공식 Python SDK는 Max 플랜 미지원, CLI wrapping 필요

**보조 엔진: Ollama 로컬**

- 대량 반복 작업용 (용어 주석 사전 생성, 단순 제목 정리)
- Max 한도 초과 자동 fallback
- 권장 모델: `qwen2.5:14b` (한국어 품질 양호) 또는 `llama3.1:8b`

**하이브리드 원칙**

| 작업 | 엔진 | 이유 |
|------|------|------|
| 뉴스·공시 2줄 요약 | Claude | 품질 차이 큼, 빈도 낮음 (하루 수십 건) |
| 용어 주석 생성 (최초) | Claude | 공시 유형당 한 번만 생성 후 DB 캐시 |
| 용어 주석 조회 | DB 캐시 | LLM 호출 불필요 |
| 밸류체인 분석 | Claude | 복잡한 추론 필요 |
| 반복 구조화 (JSON 추출 등) | Ollama 가능 | 품질 민감도 낮음 |

### 3.3 외부 API

| 서비스 | 용도 | 비용 | 제한 |
|--------|------|------|------|
| DART Open API | 국내 전자공시 | 무료 | 10,000 req/일 |
| 카카오 OAuth + Memo | 본인 카카오톡 전송 | 무료 | 4KB/메시지, talk_message scope |
| SEC EDGAR (Week 2+) | 미국 filings | 무료 | 10 req/초 |
| 네이버 금융 (크롤링, Week 3+) | 수급 데이터 | 무료 | robots.txt 준수, 완만한 속도 |
| 인포스탁 (크롤링, Week 3+) | 테마주 분류 | 무료 | 마찬가지 |

## 4. 디렉토리 구조 (권장)

```
news_briefing/
├── CLAUDE.md                 # Claude Code 프로젝트 가이드
├── README.md                 # 프로젝트 개요
├── docs/                     # 설계 문서
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   └── SIGNALS.md
├── pyproject.toml            # 프로젝트 메타 & 의존성 (uv 권장)
├── .env.example
├── .gitignore                # .env, .kakao_tokens.json, *.db 제외
│
├── src/
│   └── news_briefing/
│       ├── __init__.py
│       ├── config.py         # 환경 변수 로딩, 상수
│       ├── cli.py            # 엔트리 포인트 (morning/weekly/dryrun)
│       │
│       ├── collectors/
│       │   ├── __init__.py
│       │   ├── base.py       # 공통 인터페이스
│       │   ├── dart.py
│       │   ├── rss.py
│       │   └── edgar.py      # Week 2+
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── db.py         # SQLite 연결·스키마
│       │   ├── seen.py       # 중복 제거
│       │   └── cache.py      # LLM 응답 캐시
│       │
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── llm.py        # Claude CLI / Ollama switcher
│       │   ├── scoring.py    # 시그널 점수 산정
│       │   ├── glossary.py   # 용어 주석 (Week 2+)
│       │   └── valuechain.py # 테마·밸류체인 (Week 3+)
│       │
│       └── delivery/
│           ├── __init__.py
│           ├── kakao.py      # 나에게 보내기 + 토큰 관리
│           ├── kakao_auth.py # OAuth 1회 스크립트
│           └── web.py        # JSON 데이터 + PWA 빌드 (Week 2+)
│
├── templates/                # Jinja2 HTML 템플릿 (Week 2+)
│   ├── briefing.html
│   └── card.html
│
├── data/                     # 런타임 데이터 (gitignore)
│   ├── briefing.db
│   ├── digests/              # 일자별 백업
│   └── web/                  # 생성된 JSON 호스팅 디렉토리
│
├── scripts/
│   ├── com.user.news-briefing.morning.plist     # 평일 06:00
│   └── com.user.news-briefing.weekly.plist      # 일요일 23:00 (Week 4+)
│
└── tests/
    ├── test_scoring.py
    └── test_collectors.py
```

## 5. 핵심 데이터 모델

### 5.1 `seen` 테이블

중복 알림 방지. 한 번 처리한 항목은 다시 알림 보내지 않는다.

```sql
CREATE TABLE seen (
    source TEXT NOT NULL,      -- 'dart', 'rss:hankyung', 'edgar' 등
    ext_id TEXT NOT NULL,      -- DART rcept_no, RSS guid 등
    seen_at TEXT NOT NULL,     -- ISO 8601
    PRIMARY KEY (source, ext_id)
);
CREATE INDEX idx_seen_time ON seen(seen_at);
```

### 5.2 `llm_cache` 테이블

같은 내용에 대해 LLM을 중복 호출하지 않는다.

```sql
CREATE TABLE llm_cache (
    content_hash TEXT PRIMARY KEY,   -- SHA256(task + input)
    task TEXT NOT NULL,              -- 'summarize', 'glossary', 'valuechain'
    output TEXT NOT NULL,
    model TEXT NOT NULL,             -- 'claude-cli', 'ollama:qwen2.5:14b'
    created_at TEXT NOT NULL
);
```

### 5.3 `glossary` 테이블 (Week 2+)

공시 유형별 용어 해설.

```sql
CREATE TABLE glossary (
    term TEXT PRIMARY KEY,       -- '임원·주요주주특정증권등소유상황보고서'
    short_label TEXT NOT NULL,   -- '내부자 매매'
    explanation TEXT NOT NULL,   -- 3~4줄 해설
    signal_direction TEXT,       -- 'positive'|'negative'|'neutral'|'mixed'
    updated_at TEXT NOT NULL
);
```

### 5.4 `theme_valuechain` 테이블 (Week 3+)

테마-밸류체인-기업 매핑.

```sql
CREATE TABLE themes (
    theme_id TEXT PRIMARY KEY,       -- 'robotics', 'ai_chip'
    name_ko TEXT NOT NULL,
    description TEXT
);

CREATE TABLE value_layers (
    layer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id TEXT NOT NULL REFERENCES themes(theme_id),
    name TEXT NOT NULL,              -- '액추에이터', '센서', '제어·AI'
    description TEXT
);

CREATE TABLE companies_in_layer (
    layer_id INTEGER REFERENCES value_layers(layer_id),
    ticker TEXT NOT NULL,            -- '005930', 'NVDA' 등
    company_name TEXT NOT NULL,
    positioning TEXT,                -- LLM 생성: "이 회사가 왜 이 레이어에 속하는지"
    PRIMARY KEY (layer_id, ticker)
);
```

## 6. PWA 프론트엔드 아키텍처 (F16, F25, F26)

### 6.1 구조 개요

백엔드가 매일 JSON 데이터를 생성하고, 프론트엔드는 **단일 앱 셸** 이 이 JSON을 받아 렌더링한다. 사용자는 앱처럼 느끼지만 실제로는 웹 기술.

```
사용자 디바이스
├─ App Shell (index.html + JS bundle)   ← 한 번 로드 후 캐시
├─ Service Worker (sw.js)               ← 오프라인 요청 가로채서 캐시 응답
└─ Manifest (manifest.json)             ← 홈 화면 설치 메타데이터

서버 (Vercel/GitHub Pages)
├─ /briefings/2026-04-21.json           ← 오늘 데이터
├─ /briefings/2026-04-20.json           ← 어제
├─ /briefings/index.json                ← 날짜 목록
└─ /static/...                          ← 정적 리소스
```

### 6.2 스택

| 영역 | 선택 | 이유 |
|------|------|------|
| 프레임워크 | Next.js 15 (static export) | App Router, static generation, PWA 플러그인 성숙 |
| UI | React 19 + Tailwind CSS | `DESIGN.md` 참고 코드가 React 기반 |
| 상태 | React hooks + SWR (데이터 페칭) | SWR이 오프라인·캐시 처리 자연스러움 |
| PWA | `next-pwa` 또는 수동 SW | manifest + service worker 자동화 |
| 호스팅 | Vercel 무료 티어 | HTTPS 필수, 자동 배포 |

### 6.3 프론트엔드 디렉토리 구조

```
frontend/
├── package.json
├── next.config.js              # static export, PWA 설정
├── tailwind.config.js          # DESIGN.md 팔레트 반영
├── public/
│   ├── manifest.json
│   ├── icons/                  # 192×192, 512×512 등
│   └── briefings/              # 백엔드가 여기에 JSON 쓰기 (symlink)
├── src/
│   ├── app/
│   │   ├── layout.tsx          # 앱 셸 (헤더·탭 네비게이션)
│   │   ├── page.tsx            # 오늘 브리핑 (기본 라우트)
│   │   └── [date]/page.tsx     # 특정 날짜 브리핑
│   ├── components/
│   │   ├── SignalCard.tsx
│   │   ├── HeroCard.tsx
│   │   ├── TabBar.tsx
│   │   ├── CurrentNewsCard.tsx # 시사 탭용 (점수 없음)
│   │   ├── MarketIndices.tsx
│   │   ├── GlossaryPopover.tsx
│   │   └── InstallPrompt.tsx
│   ├── lib/
│   │   ├── fetchBriefing.ts    # JSON 로드 + SWR
│   │   ├── i18n.ts             # ko/en 전환
│   │   └── theme.ts            # 다크 모드 토글
│   └── styles/
│       └── globals.css
└── service-worker.ts           # 오프라인 캐싱 전략
```

### 6.4 JSON 데이터 스키마

백엔드 → 프론트엔드 계약. 이 스키마가 바뀌면 마이그레이션 필요.

```typescript
// /briefings/YYYY-MM-DD.json
interface Briefing {
  date: string;                  // "2026-04-21"
  generatedAt: string;           // ISO timestamp
  version: number;               // 스키마 버전
  
  hero: SignalItem | null;       // 오늘 가장 중요한 것 (점수 90+)
  
  tabs: {
    current: {                   // 시사 탭 (default, 좌측)
      politics: NewsItem[];
      society: NewsItem[];
      international: NewsItem[];
      tech: NewsItem[];
    };
    economy: {                   // 경제 탭 (중앙, Week 2a 카톡 딥링크 타겟)
      indices: MarketIndex[];    // KOSPI, NASDAQ, USD/KRW
      signals: SignalItem[];     // 점수 60+ 공시 (DART + SEC EDGAR)
      news: NewsItem[];          // 경제 뉴스 (한경·매경 등)
      themeBanner?: {            // Week 4+ 추가, 없으면 미표시
        trendingThemes: string[]; // ["로봇", "AI 반도체", "2차전지"]
        reportUrl: string;        // "/report/2026-W17"
      };
    };
    picks: {                     // 종목 탭 Today's Pick (우측, DECISIONS #12, Week 2b)
      domestic: SignalItem[];    // 국내 시그널 상위 6건 (DART)
      foreign: SignalItem[];     // 해외 시그널 상위 6건 (SEC EDGAR)
    };
  };
}

interface SignalItem {
  id: string;
  source: 'dart' | 'edgar';
  company: string;
  companyCode: string | null;    // 종목코드 (차트·딥링크용)
  headline: string;
  summary: string;
  score: number;
  direction: 'positive' | 'negative' | 'mixed' | 'neutral';
  scope: 'domestic' | 'foreign'; // 국내/해외 필터용
  time: string;
  url: string;
  glossaryTermId: string | null; // glossary 테이블 참조
}

interface NewsItem {
  id: string;
  source: string;
  title: string;
  summary: string;
  url: string;
  thumbnail: string | null;
  time: string;
  scope: 'domestic' | 'foreign'; // 국내/국제 필터용
  glossaryTermId: string | null;
  curationScore: number;         // 시사 탭용 큐레이션 점수
}
```

**언어별 캐시**: 영어 모드는 별도 파일 (`briefings/2026-04-21.en.json`) 또는 동일 파일에 `ko/en` 필드 병기. Week 2 착수 시 결정.

### 6.5 서비스 워커 캐싱 전략

| 리소스 | 전략 | 이유 |
|--------|------|------|
| App shell (HTML, JS, CSS) | **Cache first** | 업데이트 빈도 낮음, 빠른 재방문 |
| 폰트, 아이콘 | **Cache first** | 거의 변경 없음 |
| `/briefings/*.json` | **Network first, fallback cache** | 최신이 우선, 오프라인 시 캐시 |
| TradingView iframe | **Network only** | 실시간 데이터, 캐시 의미 없음 |
| 외부 이미지 (썸네일) | **Stale-while-revalidate** | 빠른 응답 + 백그라운드 갱신 |

업데이트 시점: `briefings/index.json`의 날짜 목록이 바뀌면 신규 JSON 자동 프리패치.

### 6.6 설치 프롬프트 (F25)

- `beforeinstallprompt` 이벤트 캐치 → 커스텀 UI 로 표시
- 목업 하단의 "홈 화면에 추가해보세요" 배너
- 사용자 dismiss 시 localStorage에 기록, 7일간 재표시 금지
- iOS Safari는 이 이벤트 미지원 → 수동 안내 ("공유 → 홈 화면에 추가")

### 6.7 탭 네비게이션 (F24)

- 라우팅: URL 쿼리 (`/?tab=current`) 또는 해시 (`#/current`). SSG 호환성 위해 쿼리 선호
- 탭 전환 시 페이지 리로드 없음 (클라이언트 사이드)
- 탭별 스크롤 위치 기억 (`scrollRestoration`)
- 키보드: 좌/우 화살표 키로 탭 전환

### 6.8 iOS·Android·Desktop 동작 차이

| 항목 | iOS Safari | Android Chrome | Desktop Chrome/Edge |
|------|-----------|---------------|---------------------|
| 홈 화면 설치 | ✅ (수동 안내) | ✅ (자동 프롬프트) | ✅ (주소창 아이콘) |
| 오프라인 캐시 | ✅ | ✅ | ✅ |
| 푸시 알림 | iOS 16.4+ ✅ | ✅ | ✅ |
| 네이티브 스플래시 | ✅ (apple-touch-icon) | ✅ (manifest) | N/A |
| 상태바 색상 | ✅ (`theme-color`) | ✅ | 윈도우 프레임 색상 |

iOS 푸시는 제공 가능하지만 **이 프로젝트에서는 카카오가 주 채널**이라 선택 기능으로만.

## 7. 차트·딥링크 (F18, F19)

### 7.1 TradingView 위젯 임베드 (차트)

각 종목 카드에 TradingView 위젯을 임베드한다. 공식 Embed Widget 사용, 별도 API 키 불필요.

**심볼 매핑**
- 한국 상장사: `KRX:{종목코드}` (예: `KRX:005930`)
- 미국 나스닥: `NASDAQ:{ticker}` (예: `NASDAQ:NVDA`)
- 미국 NYSE: `NYSE:{ticker}`
- DART `corp_code` → 종목코드 매핑 테이블 필요 (DART 기업 개황 API로 구축)

**위젯 크기**
- 데스크탑: 카드 확장 시 500×300
- 모바일: 340×220

**제한**
- 한국 종목은 기본 15분 지연 (TradingView 정책)
- 장중 실시간이 필수면 딥링크로 증권사 앱 이동

### 7.2 증권사 딥링크 (F19)

각 카드 하단에 "열기" 버튼 세 개. 한국 상장사 기준:

| 증권사 | 딥링크 스킴 | 비고 |
|--------|------------|------|
| 토스증권 | `supertoss://stock/{종목코드}` | iOS/Android 지원 |
| 증권플러스 | `koreainvestment://stock/{종목코드}` | 설치 필요 |
| 네이버 증권 | `https://m.stock.naver.com/domestic/stock/{종목코드}/total` | 웹, 앱 설치 시 앱으로 열림 |

딥링크 생성 모듈 (`delivery/deeplinks.py`) 에서 종목코드별로 모든 딥링크 동시 생성. UI에서는 사용자가 선호 증권사 하나를 기본값으로 설정.

### 7.3 한국투자증권 KIS API (F20, 선택·Week 5+)

Week 4까지 완료 후 "실시간 호가·체결 데이터"가 정말 필요할 때만 고려.

**요구사항**
- 한국투자증권 비대면 계좌 (무료)
- KIS Developers 가입 → 앱키·앱시크릿 발급
- REST API: 현재가, 일별 시세
- WebSocket: 실시간 체결·호가 (초당 호출 제한)

**주의**
- 계좌 정보 조회·주문 권한이 같은 앱키에 묶여 있음. **읽기 전용 앱키 별도 발급 권장.** 자동매매는 하지 않으므로 주문 권한은 필요 없음
- 앱키는 노출 시 매매도 가능하므로 `.env` 보안 필수

## 8. 관측·운영

- **로깅**: Python `logging`, stdout + `data/briefing.log`. launchd가 stdout을 파일로 리다이렉트
- **상태 확인**: `python -m news_briefing.cli status` — 마지막 실행 시각, 미처리 큐 사이즈
- **테스트 모드**: `python -m news_briefing.cli morning --dry-run` — 카톡 전송 없이 stdout으로 출력
- **실패 알림**: 연속 3회 실패 시 카톡으로 "브리핑 시스템 이상" 자동 발송

## 9. 보안

- `.env`, `.kakao_tokens.json`, `*.db` 모두 `.gitignore`
- API 키는 환경 변수로만 주입, 코드에 하드코딩 금지
- `ANTHROPIC_API_KEY` 환경 변수는 **설정하지 않음** (Claude Code가 Max 플랜 대신 API 과금 사용하게 되는 흔한 실수)
- 공개 데이터만 다루므로 분석 데이터의 외부 전송에는 민감 이슈 없음
