'use client'

import { useEffect, useState } from 'react'
import { fetchDiscovery } from '@/lib/fetchBriefing'
import type { Discovery, DiscoveryItem } from '@/lib/types'
import { StockLogo } from '@/components/StockLogo'

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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{label}</span>
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
  const logoScope = item.scope === 'kospi' ? 'domestic' : 'foreign'
  const m = item.metrics

  return (
    <div>
      {/* 헤더: 종목명 + 종합 점수(히어로) */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0, flex: 1 }}>
          <StockLogo ticker={item.ticker} name={item.name ?? item.ticker} size={26} />
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 17,
                fontWeight: 700,
                color: 'var(--text-primary)',
                letterSpacing: '-0.02em',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {item.name ?? item.ticker}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
              {item.ticker}
              {item.sector ? ` · ${item.sector}` : ''}
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
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3 }}>종합 점수</div>
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
          가치 {item.valueScore ?? '—'} · 우량 {item.qualityScore ?? '—'} · 성장{' '}
          {item.growthScore ?? '—'}
        </span>
      </div>

      {/* 핵심 지표 */}
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
        <Metric label="PER(선행)" value={mult(m.forwardPe ?? m.trailingPe)} />
        <Metric label="PBR" value={mult(m.priceToBook)} />
        <Metric label="PEG" value={mult(m.peg)} />
        <Metric label="ROE" value={pct(m.roe)} />
        <Metric label="영업이익률" value={pct(m.operatingMargin)} />
        <Metric label="매출성장" value={pct(m.revenueGrowth)} />
        <Metric label="EV/EBITDA" value={mult(m.evToEbitda)} />
        <Metric label="이익성장" value={pct(m.earningsGrowth)} />
        <Metric label="부채비율" value={pctRaw(m.debtToEquity)} />
      </div>

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

function Section({ title, items }: { title: string; items: DiscoveryItem[] }) {
  if (items.length === 0) return null
  return (
    <section className="mx-4 mb-2.5" style={{ marginBottom: 10 }}>
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: 'var(--text-tertiary)',
          padding: '0 4px 12px',
        }}
      >
        {title}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
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
    </section>
  )
}

export function DiscoveryView() {
  const [data, setData] = useState<Discovery | null>(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchDiscovery().then((d) => {
      if (cancelled) return
      setData(d)
      setLoaded(true)
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

  return (
    <div style={{ padding: '16px 0 40px' }}>
      <div
        style={{
          fontSize: 13,
          color: 'var(--text-tertiary)',
          lineHeight: 1.6,
          margin: '0 20px 16px',
        }}
      >
        오늘 뉴스에 안 나와도, 재무가 조용히 좋은 종목을 정량으로 추렸어요. 촉매가 아니라
        펀더멘털로 본 후보예요.
      </div>
      <Section title="🔍 미국 발굴" items={data.us} />
      <Section title="🇰🇷 코스피 발굴" items={data.kospi} />
    </div>
  )
}
