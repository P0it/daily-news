'use client'

import { useState } from 'react'
import type { Direction, SignalItem, ThesisCheck } from '@/lib/types'
import { GlossaryPopover } from './GlossaryPopover'

type ToneKey = 'signal.positive' | 'signal.negative' | 'signal.mixed' | 'signal.neutral'
const TONE: Record<Direction, { color: string; labelKey: ToneKey }> = {
  positive: { color: '#3182F6', labelKey: 'signal.positive' },
  negative: { color: '#F04452', labelKey: 'signal.negative' },
  mixed: { color: '#F79A34', labelKey: 'signal.mixed' },
  neutral: { color: '#8B95A1', labelKey: 'signal.neutral' },
}

function formatTime(iso: string, lang: 'ko' | 'en' = 'ko'): string {
  const d = new Date(iso)
  return d.toLocaleTimeString(lang === 'ko' ? 'ko-KR' : 'en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

// ── ThesisCheck 탭 ────────────────────────────────────────────────────────────

type ThesisTab = 'prepricing' | 'risks' | 'timing'

const TAB_LABELS: Record<ThesisTab, string> = {
  prepricing: '이미 반영됐나요?',
  risks: '어떤 위험이 있나요?',
  timing: '지금 들어가도 될까요?',
}

const PREPRICING_COLOR: Record<string, string> = {
  '이미 반영됨': '#F04452',
  '어느 정도 반영됨': '#F79A34',
  '아직 반영 안 됨': '#3182F6',
}

const TIMING_COLOR: Record<string, string> = {
  '지금 가능': '#3182F6',
  '좀 더 기다려요': '#F04452',
  '조건 충족 시 진입': '#F79A34',
}

function ThesisContent({ check, tab }: { check: ThesisCheck; tab: ThesisTab }) {
  if (tab === 'prepricing') {
    return (
      <div style={{ paddingTop: 14 }}>
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: PREPRICING_COLOR[check.prepricing] ?? 'var(--text-secondary)',
            display: 'block',
            marginBottom: 8,
          }}
        >
          {check.prepricing}
        </span>
        {check.prepricing_reason && (
          <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text-secondary)', margin: 0 }}>
            {check.prepricing_reason}
          </p>
        )}
      </div>
    )
  }

  if (tab === 'risks') {
    return (
      <div style={{ paddingTop: 14 }}>
        <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
          {check.risks.map((risk, i) => (
            <li
              key={i}
              style={{
                fontSize: 14,
                lineHeight: 1.7,
                color: 'var(--text-secondary)',
                marginBottom: 6,
                paddingLeft: 14,
                position: 'relative',
              }}
            >
              <span style={{ position: 'absolute', left: 0, color: 'var(--text-tertiary)' }}>·</span>
              {risk}
            </li>
          ))}
        </ul>
        {check.macro_links.length > 0 && (
          <div style={{ marginTop: 12 }}>
            {check.macro_links.map((link, i) => (
              <p key={i} style={{ fontSize: 13, color: 'var(--text-tertiary)', margin: '0 0 4px' }}>
                <span style={{ fontWeight: 700, color: 'var(--text-secondary)' }}>{link.factor}</span>
                {' — '}
                {link.impact}
              </p>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{ paddingTop: 14 }}>
      <span
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: TIMING_COLOR[check.timing] ?? 'var(--text-secondary)',
          display: 'block',
          marginBottom: 8,
        }}
      >
        {check.timing}
      </span>
      {check.timing_condition && (
        <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text-secondary)', margin: 0 }}>
          {check.timing_condition}
        </p>
      )}
    </div>
  )
}

// ── SignalCard ────────────────────────────────────────────────────────────────

export function SignalCard({
  signal,
  dict,
}: {
  signal: SignalItem
  dict: import('@/lib/i18n/ko').Dict
}) {
  const tone = TONE[signal.direction]
  const time = formatTime(signal.time)
  const [expanded, setExpanded] = useState(false)
  const [activeTab, setActiveTab] = useState<ThesisTab>('prepricing')
  const hasThesis = !!signal.thesisCheck

  return (
    <article
      className="mx-4 mb-2.5"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card)',
        padding: '22px 22px 18px',
      }}
    >
      {/* 방향 dot + 시간 */}
      <div className="flex items-center mb-4" style={{ gap: 7 }}>
        <span
          aria-label={dict[tone.labelKey]}
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: tone.color,
            display: 'inline-block',
          }}
        />
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: tone.color,
            letterSpacing: '-0.01em',
          }}
        >
          {dict[tone.labelKey]}
        </span>
        <span
          className="ml-auto"
          style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-tertiary)' }}
        >
          {time}
        </span>
      </div>

      {/* 기업명 + 헤드라인 + 요약 */}
      <h3
        style={{
          fontSize: 20,
          fontWeight: 700,
          letterSpacing: '-0.03em',
          lineHeight: 1.25,
          color: 'var(--text-primary)',
          marginBottom: 8,
        }}
      >
        {signal.company || '—'}
      </h3>
      <p
        style={{
          fontSize: 15,
          fontWeight: 600,
          letterSpacing: '-0.01em',
          color: 'var(--text-secondary)',
          marginBottom: 10,
        }}
      >
        {signal.headline}
      </p>
      {signal.summary && (
        <p
          style={{
            fontSize: 14,
            lineHeight: 1.7,
            color: 'var(--text-secondary)',
          }}
        >
          {signal.summary}
        </p>
      )}

      {signal.glossaryTermId && (
        <GlossaryPopover termId={signal.glossaryTermId} dict={dict} />
      )}

      {/* 푸터: 리스크 분석 토글 + 더보기 링크 */}
      <div
        className="flex items-center"
        style={{
          marginTop: 20,
          paddingTop: 14,
          borderTop: '1px solid var(--border-subtle)',
        }}
      >
        {hasThesis && (
          <button
            onClick={() => setExpanded((v) => !v)}
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--text-tertiary)',
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            {expanded ? '▴ 접기' : '▾ 리스크 분석'}
          </button>
        )}
        <a
          href={signal.url}
          target="_blank"
          rel="noopener"
          className="ml-auto"
          style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}
        >
          {dict['cta.more']}
        </a>
      </div>

      {/* ThesisCheck 확장 영역 */}
      {hasThesis && expanded && signal.thesisCheck && (
        <div style={{ marginTop: 18 }}>
          {/* 탭 헤더 */}
          <div
            className="flex"
            style={{ borderBottom: '1px solid var(--border-subtle)' }}
          >
            {(Object.keys(TAB_LABELS) as ThesisTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  fontSize: 12,
                  fontWeight: activeTab === tab ? 700 : 500,
                  color: activeTab === tab ? 'var(--text-primary)' : 'var(--text-tertiary)',
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === tab
                    ? '2px solid var(--text-primary)'
                    : '2px solid transparent',
                  padding: '0 0 10px',
                  marginRight: 14,
                  marginBottom: -1,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {TAB_LABELS[tab]}
              </button>
            ))}
          </div>

          {/* 탭 내용 */}
          <ThesisContent check={signal.thesisCheck} tab={activeTab} />
        </div>
      )}
    </article>
  )
}
