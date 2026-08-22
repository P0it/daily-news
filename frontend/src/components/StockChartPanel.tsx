'use client'

import { useEffect, useState } from 'react'
import { TradingViewWidget } from '@/components/TradingViewWidget'

type StockQuote = { price: string; change: string; changeRate: string; isUp: boolean; currency?: string }

/**
 * 종목 차트 펼침 패널 — picks·발굴 공용.
 * 부모가 open 상태와 📊 버튼을 소유하고, 펼쳐질 때만 이 패널을 렌더한다.
 *
 * @param code 시세·차트 API 용 코드 (KRX는 6자리, 미국은 티커). 발굴 KOSPI는 .KS 제거한 값
 * @param symbol TradingView 심볼 (KRX:005930 또는 NVDA)
 * @param isKrx 국내 종목 여부 — KRX는 네이버 차트 이미지, 미국은 TradingView 위젯
 * @param name 차트 이미지 alt 용 종목명
 */
export function StockChartPanel({
  code,
  symbol,
  isKrx,
  name,
}: {
  code: string
  symbol: string
  isKrx: boolean
  name: string
}) {
  const [quote, setQuote] = useState<StockQuote | null>(null)

  useEffect(() => {
    let cancelled = false
    if (isKrx) {
      fetch(`/api/naver-stock/${code}/`)
        .then((r) => r.json())
        .then((d) => {
          if (cancelled || !d.closePrice) return
          setQuote({
            price: d.closePrice,
            change: d.compareToPreviousClosePrice,
            changeRate: d.fluctuationsRatio,
            isUp: d.compareToPreviousPrice?.code === '2',
          })
        })
        .catch(() => null)
    } else {
      fetch(`/api/yahoo-stock/${code}/`)
        .then((r) => r.json())
        .then((d) => {
          if (cancelled) return
          const meta = d?.chart?.result?.[0]?.meta
          if (!meta) return
          const price = meta.regularMarketPrice
          const prev = meta.chartPreviousClose ?? meta.previousClose
          if (!price || !prev) return
          const diff = price - prev
          setQuote({
            price: price.toFixed(2),
            change: Math.abs(diff).toFixed(2),
            changeRate: Math.abs((diff / prev) * 100).toFixed(2),
            isUp: diff >= 0,
            currency: meta.currency ?? 'USD',
          })
        })
        .catch(() => null)
    }
    return () => {
      cancelled = true
    }
  }, [code, isKrx])

  return (
    <div
      style={{
        marginTop: 4,
        paddingTop: 12,
        borderTop: '1px solid var(--border-subtle)',
      }}
    >
      {isKrx ? (() => {
        const color = quote ? (quote.isUp ? '#F04452' : '#3182F6') : 'var(--text-tertiary)'
        return (
          <a href={`https://finance.naver.com/item/main.naver?code=${code}`}
            target="_blank" rel="noopener noreferrer"
            style={{ display: 'block', borderRadius: 10, overflow: 'hidden', textDecoration: 'none' }}>
            {quote && (
              <div style={{ padding: '12px 16px 10px', background: 'var(--bg-card)' }}>
                <div style={{ fontSize: 24, fontWeight: 700, color, lineHeight: 1.2 }}>
                  {quote.price}원
                </div>
                <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>전일대비</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color }}>
                    {quote.isUp ? '▲' : '▼'} {quote.change.replace('-', '')}
                  </span>
                  <span style={{ fontSize: 13, color }}>
                    ({quote.changeRate.replace('-', '')}%)
                  </span>
                </div>
              </div>
            )}
            <img
              src={`https://ssl.pstatic.net/imgfinance/chart/item/candle/day/${code}.png`}
              alt={`${name} 차트`}
              width="100%"
              style={{ display: 'block' }}
            />
          </a>
        )
      })() : (() => {
        const color = quote ? (quote.isUp ? '#00B341' : '#F04452') : 'var(--text-tertiary)'
        const unit = quote?.currency ?? 'USD'
        return (
          <>
            {quote && (
              <div style={{ padding: '12px 16px 10px', background: 'var(--bg-card)', borderRadius: 10 }}>
                <div style={{ fontSize: 24, fontWeight: 700, color, lineHeight: 1.2 }}>
                  {quote.price} {unit}
                </div>
                <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>전일대비</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color }}>
                    {quote.isUp ? '▲' : '▼'} {quote.change}
                  </span>
                  <span style={{ fontSize: 13, color }}>
                    ({quote.changeRate}%)
                  </span>
                </div>
              </div>
            )}
            <TradingViewWidget symbol={symbol} height={280} />
          </>
        )
      })()}
    </div>
  )
}
