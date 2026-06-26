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

// 발굴 탭에서 쓰는 재무 용어 해설(고정). 대화체·느낌표 없음(DESIGN).
const TERMS: { term: string; desc: string }[] = [
  {
    term: '종합 점수',
    desc: '가치·재무·성장을 합쳐 100점 만점으로 매긴 발굴 점수예요. 세 가지를 고루 갖출수록 높아요.',
  },
  {
    term: '가치 · 우량 · 성장',
    desc: '같은 후보군 안에서 백분위로 매긴 세 항목 점수예요(0~100). 옆 종목들 대비 상대 위치예요.',
  },
  {
    term: 'PER (주가수익비율)',
    desc: '주가가 1년 이익의 몇 배인지예요. 낮을수록 이익 대비 싸요. "선행"은 올해 예상 이익 기준이에요.',
  },
  {
    term: 'PBR (주가순자산비율)',
    desc: '주가가 회사 순자산의 몇 배인지예요. 1배 아래면 장부가치보다 싸게 거래되는 거예요.',
  },
  {
    term: 'PEG',
    desc: 'PER을 이익성장률로 나눈 값이에요. 1보다 낮으면 성장 속도 대비 싸다는 뜻이에요.',
  },
  {
    term: 'EV/EBITDA',
    desc: '부채까지 포함한 기업가치가 영업현금이익의 몇 배인지예요. 낮을수록 싸요.',
  },
  {
    term: 'ROE (자기자본이익률)',
    desc: '주주 돈으로 한 해 얼마나 벌었는지예요. 높을수록 자본을 잘 굴리는 회사예요.',
  },
  {
    term: '영업이익률',
    desc: '매출에서 영업이익이 차지하는 비율이에요. 높을수록 본업 수익성이 좋아요.',
  },
  {
    term: '부채비율',
    desc: '자기자본 대비 빚의 비율이에요. 낮을수록 재무가 안정적이에요.',
  },
  {
    term: '매출성장 · 이익성장',
    desc: '1년 전 대비 매출과 이익이 얼마나 늘었는지예요. 높을수록 빠르게 크는 중이에요.',
  },
]

function TermsHelp() {
  const [open, setOpen] = useState(false)

  // 모달 열림 동안 배경 스크롤 잠금
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  return (
    <div style={{ margin: '0 16px 14px' }}>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full text-left"
        style={{
          background: 'var(--bg-inset)',
          borderRadius: 'var(--radius-card)',
          padding: '14px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 13,
          fontWeight: 700,
          color: 'var(--text-secondary)',
        }}
      >
        <span aria-hidden>📖</span>
        <span>이 지표들이 무슨 뜻인가요?</span>
        <span className="ml-auto" style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          열기
        </span>
      </button>

      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 50,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'center',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--bg-card)',
              borderTopLeftRadius: 20,
              borderTopRightRadius: 20,
              width: '100%',
              maxWidth: 520,
              maxHeight: '82vh',
              overflowY: 'auto',
              padding: '22px 22px 28px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                marginBottom: 18,
              }}
            >
              <span
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                  letterSpacing: '-0.02em',
                }}
              >
                지표 용어 설명
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="닫기"
                className="ml-auto"
                style={{
                  fontSize: 14,
                  fontWeight: 700,
                  color: 'var(--text-secondary)',
                  padding: '4px 10px',
                  background: 'var(--bg-inset)',
                  borderRadius: 8,
                }}
              >
                닫기
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {TERMS.map((t) => (
                <div key={t.term}>
                  <div
                    style={{
                      fontSize: 14.5,
                      fontWeight: 700,
                      color: 'var(--text-primary)',
                      letterSpacing: '-0.01em',
                      marginBottom: 4,
                    }}
                  >
                    {t.term}
                  </div>
                  <div
                    style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--text-secondary)' }}
                  >
                    {t.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
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

function MarketTag({ scope }: { scope: DiscoveryItem['scope'] }) {
  const isForeign = scope !== 'kospi'
  return (
    <span
      style={{
        flexShrink: 0,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '-0.01em',
        color: 'var(--badge-text)',
        background: 'var(--badge-bg)',
        borderRadius: 6,
        padding: '2px 7px',
      }}
    >
      {isForeign ? '🌐 해외' : '🇰🇷 국내'}
    </span>
  )
}

function DiscoveryRow({ item }: { item: DiscoveryItem }) {
  const m = item.metrics

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
              <MarketTag scope={item.scope} />
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

      {/* 일부 팩터 결측 안내 — 점수를 보수적으로(커버리지 페널티) 매겼음을 알림 */}
      {(item.valueScore === null ||
        item.qualityScore === null ||
        item.growthScore === null) && (
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 6 }}>
          일부 지표가 빠져 점수를 보수적으로 매겼어요
        </div>
      )}

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
      <TermsHelp />
      <CardList items={[...data.us, ...data.kospi]} />
    </div>
  )
}
