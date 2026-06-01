'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import {
  parseScopeFromSearch,
  parseDateFromSearch,
  scopeHref,
  type Scope,
} from '@/lib/tabs'
import { t, type Lang } from '@/lib/i18n'

export function ScopeFilter({ lang }: { lang: Lang }) {
  const sp = useSearchParams()
  const scope = parseScopeFromSearch(sp)
  const date = parseDateFromSearch(sp)
  const dict = t(lang)

  const options: Scope[] = ['domestic', 'foreign']

  return (
    <div className="px-5 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <div
        className="flex"
        style={{
          background: 'var(--bg-inset)',
          borderRadius: 10,
          padding: 3,
          gap: 2,
        }}
      >
        {options.map((s) => {
          const active = scope === s
          const label =
            s === 'domestic' ? dict['scope.domestic'] : dict['scope.foreign']
          const emoji = s === 'domestic' ? '🇰🇷' : '🌐'
          return (
            <Link
              key={s}
              href={scopeHref(s, date)}
              className="flex-1 text-center"
              style={{
                fontSize: 14,
                fontWeight: active ? 700 : 500,
                color: active ? 'var(--text-primary)' : 'var(--text-tertiary)',
                background: active ? 'var(--bg-card)' : 'transparent',
                borderRadius: 8,
                padding: '7px 0',
                letterSpacing: '-0.02em',
                transition: 'background 150ms ease, color 150ms ease',
                textDecoration: 'none',
              }}
            >
              {emoji} {label}
            </Link>
          )
        })}
      </div>
    </div>
  )
}
