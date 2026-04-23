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

// Week 5a (DECISIONS #13): picks 를 economy 내부로 이동
export interface EconomyTab {
  indices: MarketIndex[]
  picks: PicksSection
  signals: SignalItem[]
  news: NewsItem[]
  themeBanner?: ThemeBanner
}

export interface PicksSection {
  domestic: SignalItem[]
  foreign: SignalItem[]
}

// Scope 타입 재export — 컴포넌트들이 공통 사용
export type { Scope } from './tabs'

export type Direction = 'positive' | 'negative' | 'mixed' | 'neutral'

export interface SignalItem {
  id: string
  source: 'dart' | 'edgar'
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

export interface ThemeBanner {
  trendingThemes: string[]
  reportUrl: string
}

export interface GlossaryEntry {
  shortLabel: string
  explanation: string
  direction: Direction | null
}
