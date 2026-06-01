export interface DeeplinkSet {
  toss: string
  koreainvestment: string
  naver: string
}

export interface TickerLinkSet {
  label: string
  href: string
}

export function buildDeeplinks(stockCode: string): DeeplinkSet | null {
  if (!stockCode) return null
  return {
    toss: `supertoss://stock/${stockCode}`,
    koreainvestment: `koreainvestment://stock/${stockCode}`,
    naver: `https://m.stock.naver.com/domestic/stock/${stockCode}/total`,
  }
}

/** raw 티커 → 증권사·정보 링크 목록 (국내/해외 자동 판별) */
export function buildTickerLinks(ticker: string): TickerLinkSet[] {
  if (!ticker) return []
  const isDomestic = /^\d{6}$/.test(ticker)
  if (isDomestic) {
    return [
      { label: '토스증권', href: `supertoss://stock/${ticker}` },
      { label: '네이버증권', href: `https://m.stock.naver.com/domestic/stock/${ticker}/total` },
    ]
  }
  // 지수·환율·선물은 링크 불필요
  if (/^\^/.test(ticker) || /=X$/.test(ticker) || /=F$/.test(ticker)) return []
  // 미국 주식·ETF
  return [
    { label: '네이버증권', href: `https://m.stock.naver.com/worldstock/stock/${ticker}/total` },
    { label: 'Yahoo Finance', href: `https://finance.yahoo.com/quote/${ticker}` },
  ]
}
