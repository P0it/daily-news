export interface Briefing {
  date: string
  generatedAt: string
  version: number
  hero: SignalItem | null
  tabs: {
    current: CurrentTab
    economy: EconomyTab
    picks?: PicksTab  // Week 2b
  }
  glossary?: Record<string, GlossaryEntry>
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
  themeBanner?: ThemeBanner
}

export interface PicksTab {
  domestic: SignalItem[]
  foreign: SignalItem[]
}

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

export interface NewsItem {
  id: string
  source: string
  title: string
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
