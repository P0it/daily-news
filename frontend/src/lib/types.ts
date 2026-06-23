export interface Briefing {
  date: string
  generatedAt: string
  version: number
  tabs: {
    economy: EconomyTab
  }
  glossary?: Record<string, GlossaryEntry>
}

// 종목추천 전용 스키마(v2): 지수·리서치·ETF 보조 맥락 + picks(hotIssues)
export interface EconomyTab {
  indices: MarketIndex[]
  research?: ResearchReport[]
  etf?: EtfSnapshot[]
  hotIssues?: { domestic: HotIssue[]; foreign: HotIssue[] }
  // 관찰 리스트 — 해당 scope 픽이 0인 날만 채워진다(보조 참고).
  watchlist?: { domestic: WatchItem[]; foreign: WatchItem[] }
}

// 관찰 항목 — 강한 촉매 픽엔 못 들었지만 지켜볼 만한 그날의 공시.
export interface WatchItem {
  company: string
  code: string | null
  title: string
  score: number
  direction: Direction
  source: string
  url: string | null
}

export interface ResearchReport {
  id: string
  company: string
  companyCode: string | null
  firm: string
  reportTitle: string
  targetPrice: number
  targetPriceChange: number
  targetPricePct: number
  tpDirection: string
  direction: Direction
  score: number
  url: string
  time: string
}

export interface EtfSnapshot {
  code: string
  name: string
  theme: string
  close: number
  change: number
  changePct: number
}

// Scope 타입 재export — 컴포넌트들이 공통 사용
export type { Scope } from './tabs'

export type Direction = 'positive' | 'negative' | 'mixed' | 'neutral'

export interface ThesisCheck {
  prepricing: '이미 반영됨' | '어느 정도 반영됨' | '아직 반영 안 됨'
  prepricing_reason: string
  risks: string[]
  macro_links: Array<{ factor: string; impact: string }>
  timing: '지금 가능' | '좀 더 기다려요' | '조건 충족 시 진입'
  timing_condition: string
}

export interface SignalItem {
  id: string
  source: 'dart' | 'edgar' | 'research' | 'gov_contracts' | 'edgar_cluster' | string
  assetType?: 'stock' | 'etf'
  company: string
  companyCode: string | null
  headline: string
  summary: string
  score: number
  direction: Direction
  scope: 'domestic' | 'foreign'
  time: string
  url: string
  glossaryTermId: string | null
  thesisCheck?: ThesisCheck
  attentionPhase?: number    // 1~4
  attentionLabel?: string    // 한국어 위상 라벨
  priceLead?: number         // 시그널 전 5거래일 수익률
}

export interface MarketIndex {
  name: string
  value: string
  change: string
  direction: 'up' | 'down' | 'flat'
}

export interface DomesticEtf {
  ticker: string  // 국내 ETF 종목코드
  name: string    // 국내 ETF명
}

export interface RelatedEtf {
  ticker: string                  // ETF 코드·심볼 (불확실하면 빈 문자열)
  name: string                    // ETF명
  confidence?: 'high' | 'low'     // low면 UI에 ⚠️ 추가 확인 필요 표시 (LLM 추론 기반이라 검증용)
}

export interface TickerPick {
  ticker: string              // 미국 심볼 (코드)
  name: string                // 한국어 기업·펀드명
  description: string         // 추천 이유 1~2문장
  why_undiscovered?: string | null
  consensus_risk?: 'low' | 'medium' | 'high'
  related_etf?: RelatedEtf | null   // 종목을 많이 담은 동일 시장 ETF 1개 (해외 종목→해외 ETF, 국내 종목→국내 ETF)
  domestic: DomesticEtf | DomesticEtf[] | null
  /** 사실 검증 결과 — 'review'면 티커 형식·연결고리 추가 확인 필요 */
  verifyStatus?: 'ok' | 'review'
  /** review 사유 — 왜 추가 확인이 필요한지 한 문장 */
  verifyNote?: string
  /** 실존 양성 확인 여부 (FMP·yfinance·DB 중 하나라도 확인) — 보강용 */
  tickerConfirmed?: boolean
}

export interface HotIssue {
  rank: number
  asset: string
  assetType: 'stock' | 'theme' | 'macro'
  direction: 'positive' | 'negative' | 'mixed'
  signal: string
  picks?: TickerPick[]
  reason: string
  cautions?: string
  source: string
  url: string | null
  thesisCheck?: ThesisCheck
  /** @deprecated 구버전 JSON 호환용 */
  title?: string
}

export interface GlossaryEntry {
  shortLabel: string
  explanation: string
  direction: Direction | null
}

export interface PickRecord {
  id: string
  date: string
  ticker: string
  name: string
  scope: 'domestic' | 'foreign'
  direction: Direction
  theme: string
  rationale: string
  priceAtRec: number | null
  currency: string
  currentPrice: number | null
  currentPriceAt: string | null
  changePct: number | null
}
