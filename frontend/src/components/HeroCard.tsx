import type { SignalItem } from '@/lib/types'
import { GlossaryPopover } from './GlossaryPopover'

export function HeroCard({
  signal,
  dict,
}: {
  signal: SignalItem
  dict: import('@/lib/i18n/ko').Dict
}) {
  const color = signal.direction === 'negative' ? '#F04452' : '#3182F6'

  return (
    <article
      className="mx-4 mb-2.5"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card-lg)',
        padding: '28px 24px',
      }}
    >
      <div className="flex items-center" style={{ gap: 7, marginBottom: 22 }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: color,
            display: 'inline-block',
          }}
        />
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color,
            letterSpacing: '-0.01em',
          }}
        >
          {dict['hero.today']}
        </span>
      </div>

      <h2
        style={{
          fontSize: 24,
          fontWeight: 700,
          letterSpacing: '-0.03em',
          lineHeight: 1.3,
          color: 'var(--text-primary)',
          marginBottom: 8,
        }}
      >
        {signal.company || '—'}
      </h2>
      <p
        style={{
          fontSize: 17,
          fontWeight: 500,
          letterSpacing: '-0.01em',
          color: 'var(--text-secondary)',
          marginBottom: 24,
        }}
      >
        {signal.headline}
      </p>
      {signal.summary && (
        <p
          style={{
            fontSize: 15,
            lineHeight: 1.7,
            color: 'var(--text-secondary)',
            marginBottom: 24,
          }}
        >
          {signal.summary}
        </p>
      )}

      {signal.glossaryTermId && (
        <GlossaryPopover
          termId={signal.glossaryTermId}
          dict={dict}
          defaultOpen
        />
      )}

      <a
        href={signal.url}
        target="_blank"
        rel="noopener"
        className="block w-full text-center"
        style={{
          marginTop: 24,
          background: 'var(--text-primary)',
          color: 'var(--bg-card)',
          borderRadius: 'var(--radius-btn)',
          padding: '17px',
          fontSize: 15,
          fontWeight: 700,
        }}
      >
        {dict['cta.openOriginal']}
      </a>
    </article>
  )
}
