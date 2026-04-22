# 디자인 시스템 & UI/UX

이 문서는 구현 시 일관된 UI/UX를 만들기 위한 기준이다. Claude Code가 Week 2 이후 웹·카톡 템플릿을 구축할 때 이 문서를 참조한다.

**디자인 언어**: 토스(Toss) 디자인 철학을 기반으로 한 refined minimalism. "sparse"가 아니라 "정제된 절제". 모든 요소가 제자리에 있고 필요한 것만 있다.

## 1. 디자인 철학 (5가지 원칙)

### 1.1 Typography carries hierarchy, not chrome

중요한 것을 강조하기 위해 배지·테두리·배경색을 쌓지 않는다. **크기와 굵기 대비**만으로 위계를 만든다.

```
[잘못된 접근]
[🔴95] [국내 공시] [긴급] [↓부정]  ← 뱃지 4개로 중요도 표현
삼성전자 자기주식 취득 결정         ← 본문과 시각적 비중이 비슷
```

```
[토스식 접근]
• 지금 가장 중요해요                 ← 작은 컬러 dot + 짧은 카피 한 줄
삼성전자                            ← 24px/700, 진짜 큰 제목
자기주식 취득 결정이 올라왔어요      ← 17px/500 subheading
```

### 1.2 Conversational copy, not labels

사용자에게 **말하듯이** 쓴다. "~요" 종결어미 기본. 짧고 따뜻하게.

| 기존 | 토스식 |
|------|--------|
| "주목도 85 · 긍정 해석" | "지금 가장 중요해요" |
| "용어 해설" | "자사주 매수가 뭐예요?" |
| "전체 보기" | "전체 24건 모두 보기 →" |
| "실시간 업데이트" | "오전 6:00에 업데이트했어요" |
| "오류가 발생했습니다" | "잠깐, 불러오지 못했어요" |

심각한 이벤트도 호들갑 없이 차분하게: "횡령·배임 혐의 공시가 올라왔어요" (느낌표 금지).

### 1.3 Numbers as heroes

숫자가 의미를 전달하면 **과감하게 크게** 쓴다. 22~28px, 700, tabular-nums.

주가·지수·금액·점수 모두 해당. 작은 숫자를 옆에 보조 정보로.

### 1.4 One focused action per card

한 카드에 버튼을 3개 나란히 두지 않는다.

- 주요 CTA 하나 (풀너비, dark primary)
- 보조 액션 2개 (secondary, 병렬 배치)
- 부가 링크는 카드 하단에 `자세히 →` 한 줄

### 1.5 Generous whitespace

모바일에서도 여백을 두려워하지 않는다.

- 카드 내 padding: 22~28px
- 카드 간 간격: 10~14px
- 섹션 간 간격: 28~32px
- 페이지 상단 여백: 36px+

빼곡히 채우면 "많이 담은 것"처럼 보이지만 실제로는 **무엇 하나 눈에 안 들어온다**.

---

## 2. 색상 시스템

### 2.1 그레이 스케일 (토스 팔레트 준용)

거의 모든 UI는 이 그레이만으로 구성된다. **색상은 시그널·상태 표시에만** 쓴다.

```
--gray-900: #191F28;    /* 본문 주 텍스트 */
--gray-800: #333D4B;    /* 강조 본문 */
--gray-700: #4E5968;    /* 본문 */
--gray-600: #6B7684;    /* 보조 텍스트, 메타 */
--gray-500: #8B95A1;    /* 힌트, 비활성 */
--gray-400: #B0B8C1;    /* placeholder */
--gray-300: #D1D6DB;    /* 구분선 강 */
--gray-200: #E5E8EB;    /* 구분선 */
--gray-100: #F2F4F6;    /* 배경 soft */
--gray-50:  #F9FAFB;    /* 페이지 배경 */
```

**텍스트 위계 3단계**만 사용:
- Primary: `#191F28` (제목, 강조)
- Secondary: `#4E5968` (본문)
- Tertiary: `#6B7684` / `#8B95A1` (메타, 힌트)

### 2.2 시그널 색상 (포인트로만 사용)

```
--signal-critical: #F04452;  /* 부정 긴급 */
--signal-positive: #3182F6;  /* 긍정 (토스 블루) */
--signal-mixed:    #F79A34;  /* 복합 해석 */
--signal-neutral:  #8B95A1;  /* 중립 */
```

**사용법**: dot (6px 원) + 텍스트 레이블. 배경색·테두리·스트립 형태 금지.

```html
<!-- 올바른 방식 -->
<span>• 지금 가장 중요해요</span>  <!-- dot은 #F04452, 텍스트는 같은 색 -->

<!-- 잘못된 방식 -->
<div style="background: #F04452; padding: 4px 10px;">긴급</div>  <!-- ❌ 뱃지 -->
<div style="border-left: 3px solid #F04452;">...</div>           <!-- ❌ 스트립 -->
```

### 2.3 한국 증시 상승·하락 (특수 케이스)

```
--price-up:   #F04452;  /* 한국 관례: 빨강 */
--price-down: #3182F6;  /* 파랑 */
--price-flat: #8B95A1;
```

설정에서 "미국 관례 (green up / red down)" 토글 제공.

### 2.4 Accent 포인트

거의 모든 곳에 검정·회색을 쓰되, **다음 세 위치에만 색을 허용**:

1. 시그널 dot + 레이블 (한 카드에 한 번)
2. 주가 변화율 (숫자에만)
3. 링크·CTA 텍스트 (주 CTA 제외)

주 CTA 버튼은 **#191F28** (거의 검정). 파란 버튼을 쓰고 싶은 유혹을 참는다.

### 2.5 다크 모드 팔레트

```
--gray-900 → #F9FAFB   (primary text)
--gray-700 → #B0B8C1   (body)
--gray-500 → #8B95A1   (hint, 동일)
--gray-100 → #2C3035   (soft bg)
--gray-50  → #191F28   (page bg, warm dark — 순흑 지양)

시그널 색상은 밝은 톤으로 반전:
--signal-critical-dark: #FF6B6B
--signal-positive-dark: #4A90FF
```

## 3. 타이포그래피

### 3.1 폰트

**Pretendard Variable** 단일 폰트.

```css
font-family: 'Pretendard Variable', Pretendard, 
             -apple-system, BlinkMacSystemFont, 
             'Apple SD Gothic Neo', 'Noto Sans KR', 
             system-ui, sans-serif;

/* 숫자 */
font-variant-numeric: tabular-nums;
font-feature-settings: 'tnum';
```

토스 자체 폰트(Toss Face, Toss Product Sans)는 private이라 쓸 수 없다. Pretendard가 한국에서 사실상 표준이고 토스 디자인과 시각적으로 95% 동등하다.

### 3.2 타입 스케일 (토스식 — 과감한 위계)

기존 가이드보다 **크기 대비를 과감하게** 키운다.

| 토큰 | 크기/굵기/자간 | 용도 |
|------|----------------|------|
| `hero` | 26px / 700 / -0.03em | 페이지 헤더 카피 |
| `title-xl` | 24px / 700 / -0.03em | 히어로 카드 제목 (종목명) |
| `title-lg` | 20px / 700 / -0.03em | 섹션 제목, 카드 헤드라인 |
| `title-md` | 18px / 700 / -0.02em | 서브 카드 제목 |
| `subtitle` | 17px / 500 / -0.01em | 카드 서브헤드 |
| `body` | 15px / 400 / -0.005em | 본문 |
| `body-sm` | 14px / 400 / -0.005em | 긴 설명 |
| `caption` | 13px / 500 | 메타, 보조 정보 |
| `label` | 12px / 700 / -0.01em | 섹션 라벨 ("오늘 시장") |
| `micro` | 11~12px / 500 | 시간, 출처 |

**굵기는 두 개만**: 400 (regular), 700 (bold). 500은 제한적 사용(subheading, meta). 600 금지.

**한글 음수 자간**: 14px 이상에서 `letter-spacing: -0.01em ~ -0.03em`. 큰 글씨일수록 더 타이트하게.

**줄 높이**:
- 제목 (16px+): 1.25~1.35
- 본문: 1.6~1.7 (한글은 영문보다 약간 높게)
- 메타·캡션: 1.4

### 3.3 굵기 대비로 위계 만들기

같은 크기에서도 굵기 대비로 위계가 생긴다.

```html
<!-- 종목명 (700) + 이벤트 요약 (500) -->
<div style="font-size: 20px; font-weight: 700;">삼성전자</div>
<div style="font-size: 15px; font-weight: 600;">자사주 3,000억 매수</div>
<div style="font-size: 14px; font-weight: 400;">장내매수 방식으로 2026년 10월까지 진행...</div>
```

---

## 4. 레이아웃

### 4.1 브레이크포인트

```
mobile:  < 640px     (1열, 세로 스크롤)
tablet:  640-1024    (1열 유지, 좌우 여백 확장)
desktop: > 1024      (중앙 정렬, max-width 520~640px)
```

**데스크탑에서 3열 그리드로 흩뿌리지 않는다.** 토스 스타일은 데스크탑에서도 **모바일 레이아웃을 중앙 정렬**해 하나의 column으로 본다. 양 옆에 보조 패널이 붙는 건 대시보드 스타일이지 이 프로덕트 성격이 아니다.

**예외: 종목 탭 (Today's Pick)**. 국내/해외를 나란히 비교하기 위한 **2×컬럼** 그리드만 허용. 5.13 참조. 모바일에서는 여전히 세로 스택.

### 4.2 컨테이너 너비

- 모바일 풀너비
- 태블릿·데스크탑: `max-width: 560px` (휴대폰 비율 근사)
- 좌우 패딩: 모바일 16px, 데스크탑 0 (중앙 정렬로 여백 자동 생성)
- **종목 탭만 예외**: `max-width: 720px` (2×컬럼 그리드 fit 위해 확장, 5.13)

### 4.3 간격 시스템

```
4px  · 미세 간격 (icon + text)
8px  · 인접 요소 (카드 내 버튼 사이)
10px · 카드 간 기본
14px · 섹션 내 요소 사이
16px · 섹션 내 블록 사이
20px · 카드 내 주요 요소 사이
24px · 카드 내부 padding 최소
28px · 히어로 카드 padding
32px · 섹션 간 간격
36px · 페이지 상단 여백
```

### 4.4 Radius 시스템

```
12px · 작은 버튼, 태그
14px · 중간 버튼, inset card
16px · 카드 소
18px · 카드 중
20px · 카드 대
28px · 페이지 컨테이너 (mobile screen simulation)
```

부드럽게. 토스는 직각 모서리를 거의 쓰지 않는다.

### 4.5 그림자·테두리

**그림자 없음.** 토스는 elevation을 **배경색 대비**로 표현한다 (#F9FAFB 페이지 배경 + 흰 카드).

**테두리 없음** (또는 극도로 미묘한 구분선 0.5px / `#F2F4F6`, 카드 내부 섹션 분리에만).

---

## 5. 컴포넌트 패턴

### 5.1 히어로 카드 (오늘의 핵심 1건)

하루에 단 하나, 가장 주목해야 할 이벤트. 점수 95+ 또는 강한 negative 이벤트.

```
┌─────────────────────────────┐
│                             │
│  • 지금 가장 중요해요          │  ← 컬러 dot + 한 줄
│                             │
│  코스모신소재                  │  ← 24px/700 (종목명이 hero)
│  횡령·배임 혐의 공시이 있어요    │  ← 17px/500 (상황 요약)
│                             │
│  전 대표이사의 자금 47억 원...   │  ← 15px/400 (본문)
│                             │
│  ┌─────────────────────┐    │
│  │ 횡령·배임이 뭐예요?      │    │  ← inset, #F7F8FA
│  │ 회사 임원이 직책을...    │    │
│  └─────────────────────┘    │
│                             │
│  [공시 원문 보기]              │  ← dark primary, full-width
│  [차트 보기] [토스증권]         │  ← secondary, 2분할
│                             │
└─────────────────────────────┘
```

- 카드 전체 padding: 28px 24px
- 제목까지 margin-bottom: 22px (dot 레이블에서)
- 본문과 inset 사이: 24px
- inset과 CTA 사이: 24px

### 5.2 일반 시그널 카드

```
┌─────────────────────────────┐
│  • 긍정 시그널       오전 6:35  │
│                             │
│  삼성전자                      │  ← 20px/700
│  자사주 3,000억 원 매수 결정   │  ← 15px/600
│                             │
│  장내매수 방식으로 2026년...    │  ← 14px/400
│                             │
│  ─────────────────────────  │  ← 0.5px 구분선
│  자사주 매수가 뭐예요?  자세히 →│  ← 부가 액션, 액션은 오른쪽
└─────────────────────────────┘
```

- 카드 padding: 22px 22px 18px
- 구분선 위 margin: 20px
- 구분선은 #F2F4F6

### 5.3 섹션 헤더 (큰 섹션 구분)

```
이어서 주목할 공시         ← 20px/700
주목도 순으로 5건           ← 13px/500 gray-600
```

- padding: 28px 24px 14px
- 카운트가 아니라 **설명적 부제** 사용

### 5.4 시장 지표 카드

```
오늘 시장                  ← label (12px/700)

KOSPI      NASDAQ     환율
2,874      19,421    1,387
+0.8%      -0.3%     보합
```

- 3분할 수평 배치
- 숫자 22px/700
- 변화율은 색상 + 굵기 (700)

### 5.5 버튼 스타일

**Primary (주요 CTA)**:
```css
background: #191F28;   /* 거의 검정 — 파랑 아님 */
color: white;
padding: 17px;
border-radius: 14px;
font-size: 15px;
font-weight: 700;
```

**Secondary**:
```css
background: #F2F4F6;
color: #4E5968;
padding: 14px;
border-radius: 12px;
font-size: 14px;
font-weight: 600;
```

**Ghost (인라인)**:
```css
color: #191F28 또는 #3182F6;
font-size: 13px;
font-weight: 700;
/* 배경·테두리 없음, 텍스트 + 화살표 */
```

### 5.6 시그널 dot + 레이블

```html
<div style="display: inline-flex; align-items: center; gap: 7px;">
  <span style="width: 6px; height: 6px; background: #3182F6; border-radius: 50%; display: inline-block;"></span>
  <span style="font-size: 13px; color: #3182F6; font-weight: 700; letter-spacing: -0.01em;">긍정 시그널</span>
</div>
```

### 5.7 용어 주석 (글로서리) — **핵심 기능**

이 프로덕트의 차별화 요소. "기사를 요약해준다"는 어느 뉴스 앱이나 하지만, **"모르는 용어를 바로 풀어준다"** 는 드물다. 초심자가 검색 없이 이해할 수 있게 하는 것이 핵심 가치.

#### 5.7.1 적용 범위 (빠지면 안 되는 곳)

용어 chip은 **모든 탭의 모든 카드에** 있어야 한다. 누락 금지:

| 탭 | 용어 예시 | 누가 모르는가 |
|---|---|---|
| 증권 | 자사주 매수, 내부자 매매, 전환사채, 감자, 횡령·배임, 유상증자 | 주식 초심자 전부 |
| 시사 | 원내대표, 대법원 전원합의체, 연동형 비례대표제, 추경, 국정감사 | 정치 비전문 일반인 |
| 테마 | 밸류체인, 공통분모 섹터, 파운드리, 하모닉 감속기 | 산업 초심자 |

이 카탈로그는 `SIGNALS.md` 3절에 유지되며, 새로운 용어 발견 시 `glossary` DB 테이블에 자동 추가.

#### 5.7.2 UI 패턴: 기본 노출 인라인 + 탭 시 확장

**기존 "카드 하단 작은 링크" 방식은 폐기한다.** 그러면 초심자는 이 기능이 있는 줄도 모른다. 대신:

**A. 히어로 카드**: 용어 해설을 본문 하단에 **inset 박스로 기본 표시** (접혀있지 않음)

```
[종목명]
[이벤트 한 줄 요약]
[본문 2~3줄]

┌──────────────────────────────┐
│ 횡령·배임이 뭐예요?              │  ← 제목 (13px/700)
│ 회사 임원이 직책을 이용해 자금을   │  ← 본문 (14px/400)
│ 빼돌리는 행위예요. 거래정지까지   │
│ 이어질 수 있어 시장이 예민해요.   │
└──────────────────────────────┘

[CTA 버튼들]
```

**B. 일반 카드**: "용어 힌트 + 아이콘" chip 형태로 prominent하게 배치. 본문 바로 아래, 구분선 **위**.

```
[카드 타이틀]
[본문 요약]

┌──────────────────────────────┐
│ 💡 자사주 매수가 뭐예요?    탭 │  ← 한 줄 chip, 배경 inset
└──────────────────────────────┘
─────────────
출처 · 시간    자세히 →
```

탭(클릭) 시: chip이 확장되어 해설 표시 (`height: auto` 애니메이션, 300ms).

#### 5.7.3 Inset 해설 박스 스타일

```css
background: #F7F8FA;           /* 라이트: 카드보다 약간 짙게 */
background: #2C2C31;           /* 다크 */
border-radius: 14px;
padding: 16px 18px;

/* 제목 */
font-size: 13px;
font-weight: 700;
color: #6B7684;                /* 라이트 */
color: #8B95A1;                /* 다크 */
letter-spacing: -0.01em;
margin-bottom: 8px;

/* 본문 */
font-size: 14px;
font-weight: 400;
color: #4E5968;                /* 라이트 */
color: #B0B8C1;                /* 다크 */
line-height: 1.65;
```

#### 5.7.4 상호작용 패턴

- **첫 방문**: 모든 카드의 용어 chip이 **자동 펼침 상태** (첫 3건만, 그 이후는 접힘)
- **"이미 안다" 체크**: 사용자가 특정 용어를 탭할 때마다 "알겠어요" 버튼 노출. 누르면 해당 용어는 이후 자동 접힘 상태로 저장 (localStorage)
- **설정에서 전역 토글**: "용어 해설 기본 펼침" on/off. 기본값 on (초심자 친화)

#### 5.7.5 카피 원칙 (용어 해설 본문)

- **3~4줄 이내**. 길면 본문과 경쟁
- 전문용어가 또 나오면 괄호로 풀이: "자기주식(= 회사가 자기 주식을 소유하는 것)"
- **방향성 해석 포함**: "통상 ~으로 해석됩니다" 같은 서술형 (`SIGNALS.md` 3절 참조)
- 투자 유인 표현 금지 (금칙어 필터 적용)

예시:
> **자사주 매수가 뭐예요?**
> 회사가 자기 주식을 사들이는 결정이에요. 주주 환원이나 주가 방어 목적이 흔해요. 매수한 주식을 소각하면(= 영구 삭제) 주당 가치가 즉시 개선돼서 통상 긍정 신호로 봐요.

### 5.8 뉴스 카드 (해외, 썸네일형)

```
┌─────────────────────────────┐
│  [🟢48x48]  Bloomberg  5:22 │
│   NVDA                      │
│            NVIDIA 2분기...    │
│            TSMC CoWoS 공급... │
└─────────────────────────────┘
```

- 썸네일: 48px 정사각, radius 14px
- 왼쪽 썸네일, 오른쪽 컨텐츠 (gap 14px)
- 썸네일 색상: 실제 로고 대신 기업별 브랜드 컬러 (NVIDIA=#76B900 등)

### 5.9 탭 네비게이션 (F24)

상단 앱 셸의 주요 섹션 전환. URL 쿼리 기반 (`?tab=current` / `economy`).

**스타일: Pill segmented** (토스 홈 카테고리 UI 패턴 차용).

```
[  시사  ]  [  경제  ]              ← 활성: 흰색 배경, 비활성: 투명
```

**3-탭 체계 (DECISIONS #12 개정)**:
- `시사` (default, 좌측) — 정치·사회·국제·IT 뉴스
- `경제` (중앙) — DART 공시, 경제 뉴스, 거시 지표, (Week 4+) 테마 배너
- `종목` (우측) — **Today's Pick**. 시그널 점수 상위 종목의 국내/해외 그리드 (5.13)

**기본 진입 탭**:
- PWA 아이콘·북마크: **시사** (좌측 기본)
- 카톡 딥링크: **경제** (`?tab=economy`) — Week 2a 까지. Week 2b 완료 후 사용 패턴 관찰하여 `?tab=picks` 전환 검토

**구조**:
- 수평 버튼 나열, `gap: 8px`
- 활성 탭: 흰색 배경(라이트) / 밝은 배경(다크) + 짙은 텍스트 + `font-weight: 700`
- 비활성 탭: 투명 배경 + 회색 텍스트 + `font-weight: 600`
- 2개 탭이라 공간 여유 있음 → 각 탭 width 최소 100px, padding 크게

**Underline 스타일 쓰지 않는 이유**: 탭이 콘텐츠 성격을 **강하게** 분리하는 역할(시사 vs 경제 vs 종목). Pill이 시각적 구분이 뚜렷해 사용자가 "지금 어디 있는지" 즉시 인지. Underline은 2차 필터(국내/해외)에 사용.

**스타일 예시**:

```css
/* 컨테이너 */
display: flex;
gap: 8px;
padding: 0 20px 18px;

/* 모든 탭 공통 */
padding: 12px 24px;
border: none;
border-radius: 999px;
font-size: 15px;
letter-spacing: -0.01em;
cursor: pointer;
transition: background 150ms ease-out;
min-width: 100px;

/* 활성 */
background: #F9FAFB;
color: #191F28;
font-weight: 700;

/* 비활성 */
background: transparent;
color: #8B95A1;
font-weight: 600;
```

**애니메이션**: 탭 전환 시 배경 색 변화만 (150ms). 복잡한 애니메이션 불필요.

**탭 개수 상한**: 3개 유지 (`DECISIONS.md` #12). 4개 이상 필요하면 네비게이션 재설계 트리거 (bottom nav 또는 drawer 로 전환).

### 5.9.1 국내/해외 필터 (2차 네비게이션, F24)

각 탭 안에서 "국내만" 또는 "해외만" 보기 위한 필터. **탭과 의도적으로 다른 스타일**로 시각적 위계 구분.

```
[  시사  ]  [  경제  ]           ← 1차 (Pill)

 전체   국내   국제               ← 2차 (Text + underline, 시사 탭 예시)
  ──
```

**구조**:
- 텍스트 나열, 각 항목 사이 `gap: 20px`
- 활성: 진한 글자(primary) + 굵게(700) + **2px underline**
- 비활성: 회색(tertiary) + 일반 굵기(500), underline 없음
- 컨테이너 하단에 `0.5px solid var(--border-subtle)` 라인
- 위치: 탭 바 바로 아래, 콘텐츠 위

**스타일**:

```css
/* 컨테이너 */
display: flex;
gap: 20px;
padding: 14px 20px;
border-bottom: 0.5px solid var(--border-subtle);

/* 각 필터 (button) */
padding: 6px 0;
background: none;
border: none;
font-size: 14px;
letter-spacing: -0.01em;
cursor: pointer;
position: relative;

/* 활성 */
color: var(--text-primary);
font-weight: 700;

/* 활성 underline */
&::after {
  content: '';
  position: absolute;
  bottom: -14px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--text-primary);
  border-radius: 1px;
}

/* 비활성 */
color: var(--text-tertiary);
font-weight: 500;
```

**필터 옵션 (탭별)**:

| 탭 | 옵션 |
|----|------|
| 시사 | 전체 · 국내 · 국제 |
| 경제 | 전체 · 국내 · 해외 |
| 종목 | 필터 없음 (국내/해외를 2×컬럼 레이아웃 자체로 분리, 5.13) |

**상태 관리**:
- URL 쿼리: `?tab=economy&scope=all|domestic|foreign`
- 기본값: `all`
- 필터 변경 시 스크롤 최상단으로 리셋
- 탭 전환 시 해당 탭의 이전 필터 기억 (localStorage)

**왜 pill이 아닌 text+underline?**

1차 탭(pill)과 시각적으로 달라야 위계가 명확해짐. 같은 pill이면 "같은 계층인가?" 혼란. Text+underline은 더 가벼운 인상을 주어 "이건 탭 안의 하위 옵션"임이 자연스럽게 전달됨.

**탭/필터 합성 UI 전체 예시**:

```
┌──────────────────────────────────────┐
│  [시사]  [경제]                        │  ← pill tabs
│                                      │
│   전체   국내   국제                   │  ← text filter (시사 탭 예시)
│    ──                                 │
│─────────────────────────────────────│
│  (카드 목록)                          │
└──────────────────────────────────────┘
```

### 5.10 시사 뉴스 카드 (증권과 구분)

점수·방향성 레이블 없음. 큐레이션 기반 노출.

```
┌─────────────────────────────┐
│  연합뉴스 · 정치        6:04 │
│                             │
│  대법원 전합, 실거주 의무      │
│  3년 → 폐지 여부 심리 시작     │
│                             │
│  재건축 초과이익 환수제 관련... │
│                             │
│  ─────────────────────────  │
│  대법원 전합이 뭐예요?   더 →│
└─────────────────────────────┘
```

**증권 카드와의 차이**:
- 시그널 dot + 레이블 없음 (대신 카테고리: "정치", "사회", "국제" 가 tertiary 색상)
- 점수 뱃지 없음
- 제목 계층도 단순: 제목 17px/700, 요약 14px/400

```html
<article class="bg-white rounded-card p-[22px] pb-[18px] mx-4 mb-2.5">
  <div class="flex items-center gap-2 mb-3">
    <span class="text-xs text-gray-500 font-medium">연합뉴스 · 정치</span>
    <span class="ml-auto text-xs text-gray-500 font-medium">6:04</span>
  </div>
  <h3 class="text-[17px] font-bold text-gray-900 tracking-tight leading-snug mb-2">
    대법원 전합, 실거주 의무 3년 → 폐지 여부 심리 시작
  </h3>
  <p class="text-sm text-gray-700 leading-relaxed">
    재건축 초과이익 환수제 관련 헌법불합치 여부를 함께 심리한다고 대법원이 밝혔어요.
  </p>
  <footer class="flex items-center mt-5 pt-3.5 border-t border-gray-100">
    <span class="text-[13px] text-gray-600 font-medium">대법원 전합이 뭐예요?</span>
    <span class="ml-auto text-[13px] text-gray-900 font-bold">자세히 →</span>
  </footer>
</article>
```

### 5.11 PWA 설치 프롬프트 배너 (F25)

앱 하단 또는 특정 시점에 1회 노출. 토스처럼 절제된 스타일.

```
┌─────────────────────────────┐
│ 📱  홈 화면에 추가해보세요     │
│     앱처럼 바로 열려요         │  [설치]
└─────────────────────────────┘
```

- 배경: `#1E2127` (다크) / `#F2F4F6` (라이트)
- padding: 18px 24px
- 우측 설치 버튼: 거의 검정 (라이트 모드) / 거의 흰색 (다크 모드)
- dismiss 시 localStorage 기록, 7일 후 재등장
- iOS Safari는 `beforeinstallprompt` 미지원 → "공유 → 홈 화면에 추가" 안내 문구로 변경

### 5.12 시장 지표 카드

```
오늘 시장                         ← 라벨 (12px/700/gray-500)

KOSPI        NASDAQ       환율
2,874        19,421       1,387   ← 22px/700, tabular-nums
+0.8%        -0.3%        보합    ← 13px/700, 상승=빨강, 하락=파랑
```

- 3분할 수평 배치, `justify-content: space-between`
- 라벨 → 숫자 간격: 6px
- 숫자 → 변화율 간격: 4px
- 값이 없는 경우 "—" 대신 "보합" 으로 표시

### 5.13 종목 탭 — Today's Pick 그리드 & 컴팩트 카드 (F33, F34)

시그널 점수 상위 종목을 매일 아침 한 눈에 스캔할 수 있게 만드는 전용 뷰. `DECISIONS.md` #12.

**레이아웃 원칙**:
- 데스크탑: **2×컬럼** (좌측 "국내" / 우측 "해외"), `max-width: 720px` 컨테이너 중앙 정렬 (4.2 예외)
- 모바일: 세로 스택 — `국내` 섹션 전체 → 그 아래 `해외` 섹션 전체. 좌우 스와이프 금지
- 각 컬럼 내부는 **세로 리스트** (한 컬럼 단일 column 유지)
- 섹션 헤더: "국내" / "해외" (20/700), 서브 "Today's Pick · 6건" (13/500 gray-600)

**컴팩트 카드 구조**:

```
┌────────────────────────┐
│ • 긍정 시그널   오전 6:00│
│ 삼성전자                │  ← 18px/700
│ 자사주 3,000억 매수     │  ← 14px/500
└────────────────────────┘
```

- 카드 padding: 16px 18px (일반 카드보다 컴팩트)
- 카드 사이 gap: 8px (세로)
- 컬럼 사이 gap: 14px (데스크탑)
- 배경: 흰색 (라이트) / `#26262B` (다크)
- border 없음, shadow 없음 (`DESIGN.md` 4.5 원칙)

**점수·방향성 표시**:
- `DESIGN.md` 5.6 dot + 레이블 동일 (6px 원 + 13px/700)
- 라벨 간소화: 긍정 / 복합 / 주의 / 중립

**시간 표시**: 우측 상단 `오전 6:00` 같은 형식, 12/500 gray-500

**탭 시 아코디언 펼침** (F34):
```
┌────────────────────────┐
│ • 긍정 시그널   오전 6:00│
│ 삼성전자                │
│ 자사주 3,000억 매수     │
│ ─────────────────────  │
│ [TradingView 차트 영역]│  ← 340×220 모바일 / 500×300 데스크탑
│ ─────────────────────  │
│ [공시 원문 보기]        │  ← primary, full-width
│ [토스증권] [증권플러스] │  ← secondary, 2분할 (해외는 없음)
│ [네이버증권]            │  ← secondary
└────────────────────────┘
```

- 아코디언 애니메이션: `height: auto` 300ms, `prefers-reduced-motion` 존중
- 상태 localStorage: 어떤 카드를 펼쳤는지 세션 기억

**해외 종목 카드 차이**:
- 증권사 딥링크 미지원 → 버튼 영역에 `"해외 종목"` 12/500 회색 라벨만
- TradingView 심볼은 `NASDAQ:` / `NYSE:` prefix
- 시간 표기는 `한국 시간 기준` 작게 병기 (예: `5:22 · 미국장 마감`)

**빈 상태**:
- 전체 빈 경우 한 번에: "오늘은 조용한 종목 라인업이에요"
- 한쪽만 빈 경우 해당 컬럼에만: "해외 종목이 오늘은 조용해요"

**카피 원칙 재확인** (중요):
- **"추천" 단어 금지** (`CLAUDE.md` P1 + DECISIONS #12)
- "주목" / "Pick" 만 사용
- 섹션 헤더는 **"Today's Pick"** (영문 브랜드 네이밍 허용)
- 카드 내부 카피는 이벤트 사실 서술: "자사주 3,000억 매수", "CEO 내부자 매수"

**데스크탑 ↔ 모바일 브레이크포인트**:
- `> 720px` — 2×컬럼
- `≤ 720px` — 세로 스택

**상호작용**:
- 카드 전체가 탭 영역 (내부 별도 CTA 없음)
- 탭 시 scale(0.985) press feedback (7.1)
- 펼침 상태에서 한 번 더 탭 → 접힘

---

## 6. 카피라이팅 가이드

### 6.1 원칙

- **반말 금지, 존댓말 "~요"**
- **느낌표 금지** (!는 쓰지 않는다, 대신 차분한 강조)
- **한자어 남용 금지** — "공시된 사항을 재확인 요망" ❌ → "공시 내용을 한 번 더 확인해보세요" ✅
- **의인화된 수량 표현** — "총 24건" ❌ → "24건 모두 보기"

### 6.2 상황별 카피

| 상황 | 토스식 카피 |
|------|------------|
| 히어로 (가장 중요) | "지금 가장 중요해요" |
| 긴급 경고 | "꼭 확인해보세요" |
| 긍정 시그널 | "긍정 시그널" (간결하게) |
| 복합 해석 | "복합 시그널" |
| 부정 해석 | "주의할 공시" |
| 용어 해설 유도 | "OOO가 뭐예요?" |
| 더 읽기 | "자세히 →" |
| 전체 보기 | "전체 N건 모두 보기 →" |
| 빈 상태 | "오늘은 주목할 공시가 없어요" |
| 오류 | "잠깐, 불러오지 못했어요. 다시 시도해볼까요?" |
| 업데이트 시각 | "오전 6:00에 업데이트했어요" |

### 6.3 피해야 할 표현

| 금지 | 이유 |
|------|------|
| "긴급 속보!!" | 느낌표, 호들갑 |
| "필독!" | 강요 |
| "놓치면 손해" | 투자 유인 |
| "지금 바로 확인" | 급함 조장 |
| "상승 가능성 높음" | 예측 (SIGNALS.md 선 긋기) |
| "매수 타이밍" | 권유 |

---

## 7. 상호작용

### 7.1 탭 제스처

- **카드 전체가 탭 가능**. 내부 별도 버튼 대신 카드가 링크.
- 탭 시 살짝 scale(0.985) + background slight darken — 200ms ease-out
- 히어로 카드는 CTA가 명시적이라 카드 자체 탭 동작은 없음

### 7.2 애니메이션 원칙

**과하지 않게, 기능적으로만.**

- 페이지 진입: 카드들이 fade-in + translateY(8px), stagger 40ms
- 카드 탭: scale 0.985 (press feedback)
- 용어 팝오버: slide-up bottom sheet (모바일), fade + scale (데스크탑)
- 새 브리핑 도착 (아침 pull-to-refresh 후): subtle background pulse 1회 (2초)

**`prefers-reduced-motion: reduce` 시 모든 animation 제거.**

### 7.3 Pull-to-refresh

모바일 웹에서 지원. 당김 → 업데이트 시각 새로고침.

### 7.4 상하 스크롤만

가로 스크롤 금지 (시장 지표는 3개로 제한해서 가로 스크롤 없이 fit).

---

## 8. 다크 모드

### 8.1 전환 원칙

순흑 금지. **Warm dark** (`#191F28` 페이지 배경, `#26262B` 카드).

시스템 설정 자동 감지 (`prefers-color-scheme`) + 수동 토글.

### 8.2 다크에서 주의사항

- 시맨틱 색상은 **라이트에서 쓴 hex 그대로 쓰면 안 됨** (너무 강함). 밝은 스톱으로 반전
- 흰 배경 → `#26262B`, 페이지 `#F9FAFB` → `#191F28`
- 구분선 `#F2F4F6` → `#2F2F34`

### 8.3 CSS variable 구조

```css
:root {
  --bg-page: #F9FAFB;
  --bg-card: #FFFFFF;
  --bg-inset: #F7F8FA;
  --text-primary: #191F28;
  /* ... */
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg-page: #191F28;
    --bg-card: #26262B;
    --bg-inset: #2C2C31;
    --text-primary: #F9FAFB;
    /* ... */
  }
}
```

---

## 9. 다국어 (i18n)

### 9.1 범위 (한국어 기본 + 영어 옵션)

| 항목 | 한글 | 영어 |
|------|------|------|
| UI chrome | ✅ | ✅ |
| 섹션 헤더·레이블 | ✅ | ✅ |
| 용어 주석 | ✅ | ✅ (LLM 이중 생성) |
| 뉴스 원문 제목 | 원문 유지 | 원문 유지 |
| LLM 요약 | 한글 | 영어 (재생성) |
| 시그널 레이블 | "긍정 시그널" | "Positive" |

### 9.2 언어 토글

- 기본: 시스템 locale (ko-KR → ko, else → en)
- 수동: 설정에서 `KO / EN`
- 선택은 localStorage 저장

### 9.3 영어 카피 톤

토스의 "~요" 톤을 영어로 옮길 때는 **casual, direct** 로. 과도하게 formal하게 쓰지 않는다.

| 한글 | 영어 |
|------|------|
| "지금 가장 중요해요" | "Needs your attention" |
| "OOO가 뭐예요?" | "What is OOO?" |
| "자세히 →" | "More →" |
| "전체 모두 보기 →" | "See all N items →" |
| "잠깐, 불러오지 못했어요" | "Hmm, couldn't load that." |

### 9.4 LLM 비용 최적화

영어 요약·주석은 **사용자 토글 시에만 lazy generate** 후 `(content_hash, lang)` 키로 DB 캐시. 기본 파이프라인은 한국어만 생성.

### 9.5 폰트 처리

Pretendard Variable은 영문도 우수. 언어 전환 시 별도 폰트 교체 불필요.

---

## 10. 접근성 (a11y)

### 10.1 기본 원칙

- WCAG 2.1 AA 준수 목표
- 시맨틱 HTML (`<article>`, `<section>`, `<button>`)
- 상태·방향은 **색상 외에** 텍스트·아이콘으로도 전달

### 10.2 대비

| 조합 | 비율 | 통과 |
|------|------|------|
| `#191F28` on `#FFFFFF` | 16.1:1 | ✅ |
| `#4E5968` on `#FFFFFF` | 7.2:1 | ✅ |
| `#6B7684` on `#FFFFFF` | 4.8:1 | ✅ (본문 기준) |
| `#8B95A1` on `#FFFFFF` | 3.4:1 | 대형 텍스트만 |

### 10.3 키보드

- Tab 순서 자연스럽게
- 카드 `tabindex="0"`, Enter로 활성화
- Focus ring: 2px solid `#3182F6`, border-radius 상속

### 10.4 스크린 리더

- 시그널 dot: `aria-label="긍정 시그널"`
- 숫자: "시가총액의 0.8% 규모" 같은 맥락 포함
- 상승·하락 화살표: `↑/↓` 기호 + aria-label

### 10.5 모션 감도

`prefers-reduced-motion: reduce` → 모든 animation 즉시 제거.

---

## 11. Claude Code 참고 (구현 힌트)

### 11.1 스택

- Next.js 15 또는 정적 HTML + Jinja2 (프로젝트 복잡도 따라)
- **Tailwind CSS** 권장 (빠른 prototyping, CSS variable 친화)
- Pretendard CDN 로드

### 11.2 Tailwind 설정 예시

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Pretendard Variable', 'Pretendard', 'system-ui', 'sans-serif'],
      },
      colors: {
        gray: {
          50: '#F9FAFB', 100: '#F2F4F6', 200: '#E5E8EB',
          300: '#D1D6DB', 400: '#B0B8C1', 500: '#8B95A1',
          600: '#6B7684', 700: '#4E5968', 800: '#333D4B',
          900: '#191F28',
        },
        signal: {
          critical: '#F04452',
          positive: '#3182F6',
          mixed: '#F79A34',
          neutral: '#8B95A1',
        },
      },
      borderRadius: {
        'card-sm': '16px',
        'card': '18px',
        'card-lg': '20px',
        'btn': '14px',
      },
      fontSize: {
        'hero': ['26px', { lineHeight: '1.35', letterSpacing: '-0.03em', fontWeight: '700' }],
        'title-xl': ['24px', { lineHeight: '1.3', letterSpacing: '-0.03em', fontWeight: '700' }],
        'title-lg': ['20px', { lineHeight: '1.25', letterSpacing: '-0.03em', fontWeight: '700' }],
      },
    },
  },
}
```

### 11.3 시그널 카드 컴포넌트 (의사코드)

```tsx
function SignalCard({ signal }: { signal: Signal }) {
  const toneMap = {
    positive: { color: 'signal-positive', label: '긍정 시그널' },
    mixed:    { color: 'signal-mixed',    label: '복합 시그널' },
    critical: { color: 'signal-critical', label: '주의할 공시' },
  };
  const tone = toneMap[signal.tone];

  return (
    <article className="bg-white rounded-card p-[22px] pb-[18px] mx-4 mb-2.5">
      {/* Meta bar: dot + label + time */}
      <div className="flex items-center gap-[7px] mb-4">
        <span className={`w-1.5 h-1.5 rounded-full bg-${tone.color}`} />
        <span className={`text-[13px] font-bold text-${tone.color} tracking-tight`}>
          {tone.label}
        </span>
        <span className="ml-auto text-xs font-medium text-gray-500">
          {formatTime(signal.time)}
        </span>
      </div>

      {/* Title stack */}
      <h3 className="text-title-lg mb-2">{signal.company}</h3>
      <p className="text-[15px] font-semibold text-gray-800 mb-2.5 tracking-tight">
        {signal.headline}
      </p>
      <p className="text-sm text-gray-700 leading-[1.7] tracking-[-0.005em]">
        {signal.summary}
      </p>

      {/* Footer: glossary + read more */}
      <div className="flex items-center mt-5 pt-3.5 border-t border-gray-100">
        <span className="text-[13px] font-medium text-gray-600">
          {signal.glossaryHint}
        </span>
        <span className="ml-auto text-[13px] font-bold text-gray-900">
          자세히 →
        </span>
      </div>
    </article>
  );
}
```

### 11.4 절대 하지 말 것

- 카드에 border 또는 box-shadow 추가
- 시그널 색상을 배경색·테두리로 사용
- 16px 이상 글자에 `font-weight: 600` 사용 (700이 맞음, 500은 light 용도)
- 버튼을 파란색(`#3182F6`)으로 primary 처리
- 컴포넌트 간 간격에 `margin` 대신 `gap` 안 쓰기
- 한자어·딱딱한 명사구 카피

---

## 12. 카카오톡 메시지 템플릿

**설계 원칙: 단순 링크 알림.** 카톡은 PWA로 넘어가는 접점일 뿐이니 본문에 내용을 담지 않는다. 공들여 꾸미면 오히려 "알림이 길다"는 피로감이 생김.

### 12.1 서비스명

기본값 **"데일리 브리핑"**. `config.py` 의 `SERVICE_NAME` 상수로 분리해 쉽게 바꿀 수 있게.

### 12.2 메시지 유형

카카오 **text 템플릿** 사용 (feed 템플릿 불필요). 형식:

```python
# delivery/kakao.py — 공통 헬퍼
def compose_text(title: str, url: str, button_title: str = "열기") -> dict:
    return {
        "object_type": "text",
        "text": title,
        "link": {"web_url": url, "mobile_web_url": url},
        "button_title": button_title,
    }
```

세 가지 시나리오에서 호출만 다르게:

**A. 일반 아침 브리핑** (매일 06:00)
```
데일리 브리핑 · 4월 21일
오늘 공시 3건 · 시사 8건
```
버튼: `열기` → `https://news-briefing.vercel.app/?date=2026-04-21&tab=economy` (경제 탭 딥링크)

**B. 조용한 날** (점수 70+ 없음)
```
데일리 브리핑 · 4월 22일
오늘은 조용한 장이에요. 시사 6건만 정리됐어요.
```
버튼: `열기` → `https://news-briefing.vercel.app/?date=2026-04-22&tab=current` (시사 탭 딥링크 — 조용한 날이니 시사로 우선 유도)

**C. 주간 리포트** (일요일 23:00)
```
이번 주 주간 리포트
로봇 · AI 반도체 · 2차전지가 주목받은 한 주였어요.
```
버튼: `리포트 보기` → `https://news-briefing.vercel.app/report/2026-W17`

### 12.3 제약 확인

- 카카오 text 템플릿 본문 최대 **200자** — 위 모든 포맷 안전하게 들어감
- 이모지 사용 금지
- 느낌표 사용 금지
- 금칙어 필터 적용 (`SIGNALS.md` 5절)

### 12.4 발송 로직

```
아침 브리핑 (06:00, launchd 트리거):
  signals = fetch_today_signals(min_score=70)
  if len(signals) == 0:
      send(pattern_B)  # 조용한 날
  else:
      send(pattern_A)  # 일반 (건수 자동 삽입)

주간 리포트 (일요일 23:00):
  send(pattern_C)
```

**장중 실시간 긴급 알림은 구현하지 않음.** `PRD.md` 2.5 Non-goals 참조. 이 프로덕트는 아침 배치 브리핑에 집중한다.

---

## 13. 상태별 UI (빈·에러·로딩)

### 13.1 빈 상태 (Empty State)

사용자 실수가 아닌 **데이터 부재** 상황. 부정적으로 만들지 않는다.

**경제 탭에 시그널이 전혀 없을 때** (예: 휴장일, 공휴일)

```
     ·
   (작은 아이콘 또는 일러스트, 80×80)

오늘은 조용한 장이에요
주요 공시나 큰 뉴스가 없어요.

       [둘러볼 다른 섹션]
```

- 중앙 정렬, 상하 padding 80px
- 아이콘: 16~24px gray icon (☕ 같은 이모지 금지 — 단순 원 또는 체크 마크)
- 제목: `title-md` (18px/700), `text-primary`
- 본문: `body-sm` (14px/400), `text-secondary`
- CTA: 있으면 `ghost` 스타일 1개만

**시사 탭이 조용할 때**: "아직 오늘 새 소식이 많지 않아요. 곧 업데이트될 거예요."

**다크 모드**: 아이콘·텍스트 색만 반전, 구조는 동일.

### 13.2 로딩 상태 (Loading)

토스는 스피너를 거의 쓰지 않는다. **스켈레톤**으로 나중에 올 레이아웃을 미리 보여준다.

- 카드 자리에 같은 radius·크기의 회색 블록 (`#F2F4F6` 라이트, `#2C2C31` 다크)
- 제목 라인 자리: 70% 너비, 18px 높이, radius 6px
- 본문 라인 자리: 100%/85%, 14px 높이, radius 4px
- Shimmer 애니메이션: 1.6s loop, `translateX(-100% → 100%)` of lighter gradient
- `prefers-reduced-motion: reduce` 시 shimmer 정지, 회색 블록만 표시

**첫 로딩 시**: app shell은 즉시 표시, 데이터 부분만 스켈레톤. 탭 바·헤더는 바로 보임.

### 13.3 에러 상태 (Error)

세 가지 유형 각기 다르게 처리:

**A. 네트워크 오류 (데이터 fetch 실패)**
```
     ·
   (아이콘)

잠깐, 불러오지 못했어요
네트워크 연결을 확인해보세요.

       [다시 시도]
```
- 버튼은 secondary 스타일
- 실패 이유를 기술적 언어로 노출하지 않음

**B. 부분 실패 (예: DART 성공 / 뉴스 실패)**
- 전체 에러 화면 대신 해당 섹션만 inline 에러
- 섹션 헤더 바로 아래에 subtle 경고 바:
```
⚠ 시사 뉴스를 불러오지 못했어요. 잠시 후 자동으로 다시 시도할게요.
```
- 배경: `#FFF7E1` (amber 50), 텍스트: `#854F0B`, radius 10px, padding 12px 14px

**C. 시스템 에러 (예: 서비스 장애)**
```
     ·
   (아이콘)

브리핑을 준비하고 있어요
잠시 후 다시 확인해주세요.
```
- 기술적 에러 code·stack trace 노출 절대 금지
- 개발자가 알아야 할 때만 콘솔 로그로

### 13.4 오프라인 상태 표시

Service worker 캐시에서 로드된 경우 상단에 subtle 표시:

```
📡 오프라인 · 마지막 브리핑 (06:00)
```
- 헤더 바로 아래 얇은 바 (32px 높이)
- 배경 `#F2F4F6`, 텍스트 `#6B7684`, 12px/500
- 온라인 복구 시 자동 사라짐 + 데이터 refresh

---

## 14. 히어로 없는 날 레이아웃

히어로 카드는 **점수 90+ 이벤트가 있을 때만** 표시한다. 없는 날에는 다른 구조로 전환해야 자연스럽다.

### 14.1 패턴: 요약 큐레이션 카드로 대체

```
(header: 날짜 + 카피)
"오늘은 이런 소식이 있어요"          ← 일반 톤

(요약 카드, 히어로 없이 시작)
┌─────────────────────────┐
│ 오늘의 한 줄                  │
│ 반도체 지원법 시행령 통과로    │  ← 18px/700
│ 관련 업종 전반 주목             │
└─────────────────────────┘

(다음 섹션: 일반 시그널 카드 3~5개)
주목할 공시
...
```

### 14.2 히어로 카피 변주 (헤더 카피)

점수 분포에 따라 헤더 카피 자동 결정:

| 상황 | 카피 |
|------|------|
| 90+ 1건 | `오늘은 [종목명]을 꼭 확인해보세요` (히어로 표시) |
| 90+ 2건+ | `오늘 꼭 확인할 소식 N건이 있어요` |
| 85~89 1~2건 | `오늘은 이런 소식을 주목해보세요` |
| 60~84만 존재 | `오늘은 이런 소식이 있어요` |
| 60+ 없음 | `오늘은 조용한 장이에요` |

**원칙**: 카피가 **점수의 현실을 반영**. 별일 없는 날 "긴급!" 이라고 외치면 신뢰 무너진다.

### 14.3 시사·경제 탭은 독립적으로 활성

경제 탭이 조용하다고 해서 시사 탭까지 비활성화하지 않는다. 각 탭은 자체 상태를 가진다.

---

## 15. 참고 자료

- 토스 디자인 원칙: https://toss.im/slash-21 (SLASH 21 컨퍼런스 자료)
- Pretendard: https://github.com/orioncactus/pretendard
- 토스 프론트엔드 블로그 (카피 가이드): https://toss.tech
- TradingView Widget: https://www.tradingview.com/widget/
- WCAG 2.1 AA: https://www.w3.org/WAI/WCAG21/quickref/
- KakaoTalk 메시지 템플릿 (feed): https://developers.kakao.com/docs/latest/ko/message/message-template
