export interface Briefing {
  date: string
  generatedAt: string
  version: number
  hero: SignalItem | null
  tabs: {
    ai?: AiTab // Week 5b — default tab (DECISIONS #13)
    current: CurrentTab
    economy: EconomyTab
  }
  glossary?: Record<string, GlossaryEntry>
}

export interface AiTab {
  domestic: NewsItem[]
  foreign: NewsItem[]
}

export interface CurrentTab {
  politics: NewsItem[]
  society: NewsItem[]
  international: NewsItem[]
  tech: NewsItem[]
}

export interface EconomyTab {
  indices: MarketIndex[]
  signals: SignalItem[]
  news: NewsItem[]
  hotIssues?: { domestic: HotIssue[]; foreign: HotIssue[] }
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

export type NewsCategory =
  | 'stock'
  | 'politics'
  | 'society'
  | 'international'
  | 'tech'
  | 'ai'

export interface NewsItem {
  id: string
  source: string
  /** Google News aggregator 의 실제 원문 언론사명 (Week 5a) */
  publisher?: string
  title: string
  /** 해외 AI 뉴스 제목이 번역된 경우 원문 (Week 5b) */
  titleOriginal?: string | null
  summary: string
  url: string
  thumbnail: string | null
  time: string
  scope: 'domestic' | 'foreign'
  category?: NewsCategory
  glossaryTermId: string | null
  curationScore: number
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

export interface TickerPick {
  ticker: string              // 미국 심볼 (코드)
  name: string                // 한국어 기업·펀드명
  description: string         // 추천 이유 1~2문장
  why_undiscovered?: string | null
  consensus_risk?: 'low' | 'medium' | 'high'
  domestic: DomesticEtf | DomesticEtf[] | null
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
