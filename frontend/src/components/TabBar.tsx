'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { parseTabFromSearch, tabHref, type Tab } from '@/lib/tabs'
import { t, type Lang } from '@/lib/i18n'

export function TabBar({ lang }: { lang: Lang }) {
  const sp = useSearchParams()
  const currentTab = parseTabFromSearch(sp)
  const dict = t(lang)

  const tabs: { key: Tab; label: string }[] = [
    { key: 'current', label: dict['tab.current'] },
    { key: 'economy', label: dict['tab.economy'] },
    { key: 'picks', label: dict['tab.picks'] },
  ]

  return (
    <nav
      className="flex gap-1.5 px-5 pt-2 pb-3"
      role="tablist"
      style={{ borderBottom: '1px solid transparent' }}
    >
      {tabs.map(({ key, label }) => {
        const active = currentTab === key
        return (
          <Link
            key={key}
            href={tabHref(key)}
            role="tab"
            aria-selected={active}
            className="text-center rounded-full transition-colors"
            style={{
              padding: '7px 16px',
              fontSize: 14,
              letterSpacing: '-0.01em',
              background: active ? 'var(--bg-card)' : 'transparent',
              color: active ? 'var(--text-primary)' : 'var(--text-tertiary)',
              fontWeight: active ? 700 : 600,
            }}
          >
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
