'use client'

import { useEffect, useRef, useState } from 'react'
import { fetchDiscovery } from '@/lib/fetchBriefing'
import type { Discovery, DiscoveryItem } from '@/lib/types'
import { StockLogo } from '@/components/StockLogo'
import { StockChartPanel } from '@/components/StockChartPanel'
import { resolveTickerToSymbol } from '@/lib/tradingview'

// 비율(소수 0.18 = 18%) → 퍼센트 문자열
function pct(x: number | null, digits = 0): string {
  if (x === null) return '—'
  return `${(x * 100).toFixed(digits)}%`
}

// 배수(PER·PBR 등)
function mult(x: number | null): string {
  if (x === null) return '—'
  return x.toFixed(1)
}

// 이미 퍼센트 단위인 값(부채비율 79.5 = 79.5%)
function pctRaw(x: number | null): string {
  if (x === null) return '—'
  return `${x.toFixed(0)}%`
}

// 각 지표 라벨의 툴팁 설명(고정). 대화체·느낌표 없음(DESIGN).
const TIP = {
  composite: '가치·재무·성장을 합쳐 100점 만점으로 매긴 발굴 점수예요. 세 가지를 고루 갖출수록 높아요.',
  factors: '같은 후보군 안에서 백분위로 매긴 가치·우량·성장 점수예요(0~100). 옆 종목들 대비 상대 위치예요.',
  per: '주가가 1년 이익의 몇 배인지예요. 낮을수록 이익 대비 싸요. "선행"은 올해 예상 이익 기준이에요.',
  pbr: '주가가 회사 순자산의 몇 배인지예요. 1배 아래면 장부가치보다 싸게 거래되는 거예요.',
  peg: 'PER을 이익성장률로 나눈 값이에요. 1보다 낮으면 성장 속도 대비 싸다는 뜻이에요.',
  ev: '부채까지 포함한 기업가치가 영업현금이익(EBITDA)의 몇 배인지예요. 낮을수록 싸요.',
  roe: '주주 돈으로 한 해 얼마나 벌었는지예요. 높을수록 자본을 잘 굴리는 회사예요.',
  opm: '매출에서 영업이익이 차지하는 비율이에요. 높을수록 본업 수익성이 좋아요.',
  rev: '1년 전 대비 매출이 얼마나 늘었는지예요. 높을수록 빠르게 크는 중이에요.',
  earn: '1년 전 대비 이익이 얼마나 늘었는지예요. 높을수록 빠르게 크는 중이에요.',
  debt: '자기자본 대비 빚의 비율이에요. 낮을수록 재무가 안정적이에요.',
} as const

/** 라벨에 점선 밑줄을 달고, 호버(데스크톱)·탭(모바일)으로 설명 툴팁을 띄운다. */
function InfoTip({
  children,
  desc,
  align = 'left',
}: {
  children: React.ReactNode
  desc: string
  align?: 'left' | 'right'
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('click', onDoc)
    return () => document.removeEventListener('click', onDoc)
  }, [open])

  return (
    <span
      ref={ref}
      style={{ position: 'relative', display: 'inline-block' }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        style={{
          font: 'inherit',
          color: 'inherit',
          textAlign: 'inherit',
          textDecoration: 'underline dotted',
          textUnderlineOffset: 3,
          textDecorationColor: 'var(--text-tertiary)',
          cursor: 'help',
        }}
      >
        {children}
      </button>
      {open && (
        <span
          role="tooltip"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            [align]: 0,
            zIndex: 30,
            width: 210,
            padding: '10px 12px',
            textAlign: 'left',
            background: 'var(--bg-card)',
            color: 'var(--text-secondary)',
            borderRadius: 10,
            boxShadow: '0 6px 24px rgba(0, 0, 0, 0.18)',
            fontSize: 12.5,
            fontWeight: 400,
            lineHeight: 1.55,
            letterSpacing: '-0.01em',
            whiteSpace: 'normal',
          }}
        >
          {desc}
        </span>
      )}
    </span>
  )
}

function Metric({
  label,
  value,
  tip,
  align = 'left',
}: {
  label: string
  value: string
  tip: string
  align?: 'left' | 'right'
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
        <InfoTip desc={tip} align={align}>
          {label}
        </InfoTip>
      </span>
      <span
        style={{
          fontSize: 14,
          fontWeight: 600,
          color: 'var(--text-primary)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </span>
    </div>
  )
}

function Block({ label, text }: { label: string; text: string | null }) {
  if (!text) return null
  return (
    <div style={{ marginTop: 14 }}>
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.04em',
          color: 'var(--text-tertiary)',
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{text}</div>
    </div>
  )
}

function DiscoveryRow({ item }: { item: DiscoveryItem }) {
  const m = item.metrics
  const [chartOpen, setChartOpen] = useState(false)
  const symbol = resolveTickerToSymbol(item.ticker)
  const isKrx = symbol?.startsWith('KRX:') ?? false
  // 시세·차트 API 코드: KRX는 .KS 떼고 6자리, 미국은 티커 그대로
  const code = isKrx ? item.ticker.replace(/\.KS$/, '') : item.ticker

  return (
    <div>
      {/* 헤더: 종목명 + 시장 딱지 + 종합 점수(히어로) */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0, flex: 1 }}>
          <StockLogo ticker={item.ticker} name={item.name ?? item.ticker} size={26} />
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
              <span
                style={{
                  fontSize: 17,
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                  letterSpacing: '-0.02em',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  minWidth: 0,
                }}
              >
                {item.name ?? item.ticker}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 12,
                color: 'var(--text-tertiary)',
              }}
            >
              <span>
                {item.ticker}
                {item.sector ? ` · ${item.sector}` : ''}
              </span>
              {symbol && (
                <button
                  type="button"
                  onClick={() => setChartOpen((v) => !v)}
                  title={chartOpen ? '차트 닫기' : isKrx ? '네이버 증권 차트' : '차트 보기'}
                  style={{
                    background: chartOpen ? 'var(--bg-inset)' : 'transparent',
                    border: 'none',
                    borderRadius: 6,
                    padding: '1px 5px',
                    cursor: 'pointer',
                    fontSize: 13,
                    lineHeight: 1,
                    flexShrink: 0,
                    display: 'inline-flex',
                    alignItems: 'center',
                  }}
                >
                  📊
                </button>
              )}
            </div>
          </div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div
            style={{
              fontSize: 26,
              fontWeight: 700,
              color: 'var(--text-primary)',
              lineHeight: 1,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {item.composite}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3 }}>
            <InfoTip desc={TIP.composite} align="right">
              종합 점수
            </InfoTip>
          </div>
        </div>
      </div>

      {/* 강점 태그 + 팩터 점수 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginTop: 12,
          fontSize: 13,
          color: 'var(--text-secondary)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {item.highlights.length > 0 && (
          <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
            {item.highlights.join(' · ')}
          </span>
        )}
        <span style={{ color: 'var(--text-tertiary)' }}>
          <InfoTip desc={TIP.factors} align="left">
            가치 {item.valueScore ?? '—'} · 우량 {item.qualityScore ?? '—'} · 성장{' '}
            {item.growthScore ?? '—'}
          </InfoTip>
        </span>
      </div>

      {/* 일부 팩터 결측 안내 — 점수를 보수적으로(커버리지 페널티) 매겼음을 알림 */}
      {(item.valueScore === null ||
        item.qualityScore === null ||
        item.growthScore === null) && (
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 6 }}>
          일부 지표가 빠져 점수를 보수적으로 매겼어요
        </div>
      )}

      {/* 핵심 지표 (라벨 탭/호버 시 설명 툴팁) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '12px 8px',
          marginTop: 16,
          padding: '14px 16px',
          background: 'var(--bg-inset)',
          borderRadius: 12,
        }}
      >
        <Metric label="PER(선행)" tip={TIP.per} value={mult(m.forwardPe ?? m.trailingPe)} />
        <Metric label="PBR" tip={TIP.pbr} value={mult(m.priceToBook)} />
        <Metric label="PEG" tip={TIP.peg} align="right" value={mult(m.peg)} />
        <Metric label="ROE" tip={TIP.roe} value={pct(m.roe)} />
        <Metric label="영업이익률" tip={TIP.opm} value={pct(m.operatingMargin)} />
        <Metric label="매출성장" tip={TIP.rev} align="right" value={pct(m.revenueGrowth)} />
        <Metric label="EV/EBITDA" tip={TIP.ev} value={mult(m.evToEbitda)} />
        <Metric label="이익성장" tip={TIP.earn} value={pct(m.earningsGrowth)} />
        <Metric label="부채비율" tip={TIP.debt} align="right" value={pctRaw(m.debtToEquity)} />
      </div>

      {/* 차트 펼침 — picks 와 동일한 패널 재사용 */}
      {chartOpen && symbol && (
        <StockChartPanel code={code} symbol={symbol} isKrx={isKrx} name={item.name ?? item.ticker} />
      )}

      {/* 서술 */}
      {item.thesis && (
        <div
          style={{
            fontSize: 14.5,
            color: 'var(--text-primary)',
            lineHeight: 1.7,
            marginTop: 16,
          }}
        >
          {item.thesis}
        </div>
      )}
      <Block label="시장이 아직 안 본 이유" text={item.whyUndiscovered} />
      <Block label="확인할 신호" text={item.confirmCatalysts} />
      <Block label="짚어둘 리스크" text={item.keyRisks} />
      {item.valuationNote && (
        <div style={{ fontSize: 13, color: 'var(--text-tertiary)', marginTop: 12 }}>
          {item.valuationNote}
        </div>
      )}

      {/* ISA·연금용 국내 추종 ETF */}
      {item.relatedEtf && (
        <div
          style={{
            marginTop: 14,
            padding: '12px 14px',
            background: 'var(--bg-inset)',
            borderRadius: 10,
            fontSize: 13,
            color: 'var(--text-secondary)',
          }}
        >
          <span style={{ color: 'var(--text-tertiary)' }}>ISA·연금으로는 </span>
          <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
            {item.relatedEtf.name}
          </span>
          <span style={{ color: 'var(--text-tertiary)' }}> ({item.relatedEtf.ticker})</span>
          {item.relatedEtf.confidence === 'low' && (
            <span style={{ color: 'var(--text-tertiary)' }}> · ⚠️ 추가 확인 필요</span>
          )}
        </div>
      )}
    </div>
  )
}

function CardList({ items }: { items: DiscoveryItem[] }) {
  return (
    <div className="mx-4" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {items.map((item) => (
        <div
          key={`${item.scope}-${item.ticker}`}
          style={{
            background: 'var(--bg-card)',
            borderRadius: 'var(--radius-card)',
            padding: '20px 22px',
          }}
        >
          <DiscoveryRow item={item} />
        </div>
      ))}
    </div>
  )
}

/** 해외/국내 전환 세그먼트 — 스크롤 없이 시장을 바꿔 본다. */
function MarketToggle({
  value,
  onChange,
  counts,
}: {
  value: 'us' | 'kospi'
  onChange: (v: 'us' | 'kospi') => void
  counts: { us: number; kospi: number }
}) {
  const options: { key: 'us' | 'kospi'; label: string }[] = [
    { key: 'us', label: `🌐 해외 ${counts.us}` },
    { key: 'kospi', label: `🇰🇷 국내 ${counts.kospi}` },
  ]
  return (
    <div
      className="mx-4 flex"
      style={{ background: 'var(--bg-inset)', borderRadius: 10, padding: 3, gap: 2 }}
    >
      {options.map(({ key, label }) => {
        const active = value === key
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className="flex-1 text-center"
            style={{
              fontSize: 14,
              fontWeight: active ? 700 : 500,
              color: active ? 'var(--text-primary)' : 'var(--text-tertiary)',
              background: active ? 'var(--bg-card)' : 'transparent',
              border: 'none',
              borderRadius: 8,
              padding: '7px 0',
              letterSpacing: '-0.02em',
              cursor: 'pointer',
              transition: 'background 150ms ease, color 150ms ease',
            }}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}

export function DiscoveryView() {
  const [data, setData] = useState<Discovery | null>(null)
  const [loaded, setLoaded] = useState(false)
  // 해외 관심이 높아 기본값은 해외. 데이터 로드 후 한쪽만 있으면 그쪽으로 맞춘다.
  const [market, setMarket] = useState<'us' | 'kospi'>('us')

  useEffect(() => {
    let cancelled = false
    fetchDiscovery().then((d) => {
      if (cancelled) return
      setData(d)
      setLoaded(true)
      // 해외가 비고 국내만 있으면 국내로 시작
      if (d && d.us.length === 0 && d.kospi.length > 0) setMarket('kospi')
    })
    return () => {
      cancelled = true
    }
  }, [])

  if (!loaded) {
    return (
      <p className="px-5 py-20 text-center" style={{ color: 'var(--text-tertiary)' }}>
        불러오는 중...
      </p>
    )
  }

  if (!data || (data.us.length === 0 && data.kospi.length === 0)) {
    return (
      <p
        className="px-5 py-20 text-center"
        style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}
      >
        아직 발굴 결과가 없어요.
        <br />
        펀더멘털 스크린을 돌리면 저평가·우량·성장 종목이 여기 채워져요.
      </p>
    )
  }

  // 둘 다 있을 때만 토글을 보여준다(한쪽만 있으면 그 목록을 바로 렌더).
  const bothMarkets = data.us.length > 0 && data.kospi.length > 0
  const items = market === 'us' ? data.us : data.kospi

  return (
    <div style={{ padding: '16px 0 40px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      {bothMarkets && (
        <MarketToggle
          value={market}
          onChange={setMarket}
          counts={{ us: data.us.length, kospi: data.kospi.length }}
        />
      )}
      <CardList items={bothMarkets ? items : [...data.us, ...data.kospi]} />
    </div>
  )
}
