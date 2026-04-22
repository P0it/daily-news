export interface DeeplinkSet {
  toss: string
  koreainvestment: string
  naver: string
}

export function buildDeeplinks(stockCode: string): DeeplinkSet | null {
  if (!stockCode) return null
  return {
    toss: `supertoss://stock/${stockCode}`,
    koreainvestment: `koreainvestment://stock/${stockCode}`,
    naver: `https://m.stock.naver.com/domestic/stock/${stockCode}/total`,
  }
}
