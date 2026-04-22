import type { Direction, SignalItem } from '@/lib/types'
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

export function SignalCard({
  signal,
  dict,
}: {
  signal: SignalItem
  dict: import('@/lib/i18n/ko').Dict
}) {
  const tone = TONE[signal.direction]
  const time = formatTime(signal.time)

  return (
    <article
      className="mx-4 mb-2.5"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card)',
        padding: '22px 22px 18px',
      }}
    >
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

      <div
        className="flex items-center"
        style={{
          marginTop: 20,
          paddingTop: 14,
          borderTop: '1px solid var(--border-subtle)',
        }}
      >
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
    </article>
  )
}
