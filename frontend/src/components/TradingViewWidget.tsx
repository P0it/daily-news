'use client'

import { useEffect, useRef } from 'react'

export function TradingViewWidget({
  symbol,
  height = 260,
}: {
  symbol: string
  height?: number
}) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    // Clean any previous widget instance (e.g., on symbol change)
    el.innerHTML = ''

    const isDark = document.documentElement.classList.contains('dark')
    const script = document.createElement('script')
    script.src =
      'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js'
    script.async = true
    script.innerHTML = JSON.stringify({
      symbols: [[symbol, symbol]],
      chartOnly: true,
      width: '100%',
      height,
      locale: 'ko',
      colorTheme: isDark ? 'dark' : 'light',
      autosize: false,
      showVolume: false,
      hideDateRanges: false,
      isTransparent: true,
      noTimeScale: false,
    })
    el.appendChild(script)
    return () => {
      if (el) el.innerHTML = ''
    }
  }, [symbol, height])

  return (
    <div
      ref={containerRef}
      className="tradingview-widget-container"
      style={{ height, marginTop: 12, marginBottom: 12 }}
      aria-label={`${symbol} chart`}
    />
  )
}
