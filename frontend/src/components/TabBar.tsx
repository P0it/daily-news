'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { parseTabFromSearch, tabHref, type Tab } from '@/lib/tabs'
import { t, type Lang } from '@/lib/i18n'

export function TabBar({ lang }: { lang: Lang }) {
  const sp = useSearchParams()
  const currentTab = parseTabFromSearch(sp)
  const dict = t(lang)

  // Week 2a: 2 tabs. Week 2b 에서 'picks' 추가.
  const tabs: { key: Tab; label: string }[] = [
    { key: 'current', label: dict['tab.current'] },
    { key: 'economy', label: dict['tab.economy'] },
  ]

  return (
    <nav className="flex gap-2 px-5 pt-3 pb-4" role="tablist">
      {tabs.map(({ key, label }) => {
        const active = currentTab === key
        return (
          <Link
            key={key}
            href={tabHref(key)}
            role="tab"
            aria-selected={active}
            className={`min-w-[100px] text-center rounded-full px-6 py-3 text-[15px] tracking-tight transition-colors ${
              active
                ? 'bg-white text-gray-900 font-bold dark:bg-gray-800 dark:text-white'
                : 'bg-transparent text-gray-500 font-semibold'
            }`}
          >
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
