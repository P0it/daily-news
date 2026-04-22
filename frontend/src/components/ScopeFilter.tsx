'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import {
  parseScopeFromSearch,
  parseTabFromSearch,
  tabHref,
  type Scope,
} from '@/lib/tabs'
import { t, type Lang } from '@/lib/i18n'

export function ScopeFilter({ lang }: { lang: Lang }) {
  const sp = useSearchParams()
  const tab = parseTabFromSearch(sp)
  const scope = parseScopeFromSearch(sp)
  const dict = t(lang)

  const options: Scope[] = ['all', 'domestic', 'foreign']

  return (
    <div
      className="flex gap-5 px-5 py-3.5"
      style={{
        borderBottom: '0.5px solid var(--border-subtle)',
      }}
    >
      {options.map((s) => {
        const active = scope === s
        const label =
          s === 'all'
            ? dict['scope.all']
            : s === 'domestic'
            ? dict['scope.domestic']
            : tab === 'current'
            ? dict['scope.international']
            : dict['scope.foreign']
        return (
          <Link
            key={s}
            href={tabHref(tab, s)}
            className="relative pb-1.5 text-sm tracking-tight"
            style={{
              color: active ? 'var(--text-primary)' : 'var(--text-tertiary)',
              fontWeight: active ? 700 : 500,
            }}
          >
            {label}
            {active && (
              <span
                aria-hidden
                style={{
                  position: 'absolute',
                  left: 0,
                  right: 0,
                  bottom: '-15px',
                  height: '2px',
                  background: 'var(--text-primary)',
                  borderRadius: '1px',
                }}
              />
            )}
          </Link>
        )
      })}
    </div>
  )
}
