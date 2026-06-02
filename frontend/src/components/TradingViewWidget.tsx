'use client'

import { useEffect, useRef } from 'react'

export function TradingViewWidget({
  symbol,
  height = 400,
}: {
  symbol: string
  height?: number
}) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.innerHTML = ''

    const isDark = document.documentElement.classList.contains('dark')
    const script = document.createElement('script')
    script.src =
      'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      symbol,
      width: '100%',
      height,
      locale: 'ko',
      interval: 'D',
      timezone: 'Asia/Seoul',
      theme: isDark ? 'dark' : 'light',
      style: '1',
      hide_side_toolbar: true,
      hide_top_toolbar: true,
      hide_legend: true,
      allow_symbol_change: false,
      save_image: false,
      calendar: false,
      hide_volume: false,
    })
    el.appendChild(script)

    return () => {
      if (el) el.innerHTML = ''
    }
  }, [symbol, height])

  return (
    <div
      style={{
        borderRadius: 10,
        overflow: 'hidden',
        marginTop: 4,
        marginBottom: 4,
      }}
    >
      <div
        ref={containerRef}
        className="tradingview-widget-container"
        style={{ height }}
        aria-label={`${symbol} chart`}
      />
    </div>
  )
}
