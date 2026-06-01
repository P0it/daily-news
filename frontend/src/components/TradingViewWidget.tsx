'use client'

import { useEffect, useRef } from 'react'

export function TradingViewWidget({
  symbol,
  height = 360,
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
      'https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      symbol,
      width: '100%',
      height,
      locale: 'ko',
      dateRange: '1W',
      colorTheme: isDark ? 'dark' : 'light',
      isTransparent: false,
      autosize: false,
      noTimeScale: false,
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
