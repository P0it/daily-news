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

  // Week 5a (DECISIONS #13): 'all' 제거, 국내/해외 2옵션만
  const options: Scope[] = ['domestic', 'foreign']

  return (
    <div
      className="flex gap-5 px-5 py-3.5"
      style={{
        borderBottom: '0.5px solid var(--border-subtle)',
      }}
    >
      {options.map((s) => {
        const active = scope === s
        // Week 5b: 탭 관계없이 '국내 / 해외' 로 통일 (DECISIONS #13)
        const label =
          s === 'domestic' ? dict['scope.domestic'] : dict['scope.foreign']
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
