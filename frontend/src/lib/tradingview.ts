import type { SignalItem } from '@/lib/types'

/**
 * hot_issues picks 등 raw 티커 → TradingView 심볼 변환
 * - 6자리 숫자: KRX 종목 (KRX:005930)
 * - ^, =X, =F: 지수·환율·선물 — 차트 미지원
 * - 그 외: 미국 주식/ETF 그대로 사용
 */
export function resolveTickerToSymbol(ticker: string): string | null {
  if (!ticker) return null
  if (/^\^/.test(ticker)) return null          // 지수 (^GSPC 등)
  if (/=X$/.test(ticker)) return null          // 환율 (KRW=X 등)
  if (/=F$/.test(ticker)) return null          // 선물 (CL=F, GC=F 등)
  if (/^\d{6}$/.test(ticker)) return `KRX:${ticker}` // 국내 종목
  return ticker                                // 미국 주식/ETF
}

// SEC CIK (10자리, zero-padded) → 미국 티커 하드코딩
// Week 2b 초기. SEC company_tickers.json 전체 파싱은 Week 3+ 로 이관.
const CIK_TICKER: Record<string, { ticker: string; exchange: 'NASDAQ' | 'NYSE' }> = {
  '0001045810': { ticker: 'NVDA', exchange: 'NASDAQ' },
  '0000320193': { ticker: 'AAPL', exchange: 'NASDAQ' },
  '0001318605': { ticker: 'TSLA', exchange: 'NASDAQ' },
  '0000789019': { ticker: 'MSFT', exchange: 'NASDAQ' },
  '0001652044': { ticker: 'GOOGL', exchange: 'NASDAQ' },
  '0001018724': { ticker: 'AMZN', exchange: 'NASDAQ' },
  '0001326801': { ticker: 'META', exchange: 'NASDAQ' },
  '0000051143': { ticker: 'IBM', exchange: 'NYSE' },
  '0000200406': { ticker: 'JNJ', exchange: 'NYSE' },
  '0000019617': { ticker: 'JPM', exchange: 'NYSE' },
  '0000078003': { ticker: 'PFE', exchange: 'NYSE' },
  '0000034088': { ticker: 'XOM', exchange: 'NYSE' },
}

export function resolveTradingViewSymbol(signal: SignalItem): string | null {
  if (signal.source === 'dart' && signal.companyCode) {
    return `KRX:${signal.companyCode}`
  }
  if (signal.source === 'edgar' && signal.companyCode) {
    const paddedCik = signal.companyCode.padStart(10, '0')
    const m = CIK_TICKER[paddedCik]
    if (m) return `${m.exchange}:${m.ticker}`
  }
  return null
}
