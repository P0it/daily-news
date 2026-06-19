'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import {
  fetchBriefing,
  fetchLatestBriefing,
} from '@/lib/fetchBriefing'
import { setGlossary } from '@/lib/glossaryStore'
import { getStoredLang, t, type Lang } from '@/lib/i18n'
import { parseDateFromSearch, parseScopeFromSearch } from '@/lib/tabs'
import type { Briefing } from '@/lib/types'
import { HotIssuesCard } from '@/components/HotIssuesCard'
import { PicksHistoryView } from '@/components/PicksHistoryView'

function HomeInner() {
  const sp = useSearchParams()
  const scope = parseScopeFromSearch(sp)
  const date = parseDateFromSearch(sp)
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lang, setLang] = useState<Lang>('ko')

  useEffect(() => {
    setLang(getStoredLang())
  }, [])

  useEffect(() => {
    let cancelled = false
    async function run() {
      try {
        const b = date
          ? await fetchBriefing(date)
          : await fetchLatestBriefing()
        if (cancelled) return
        if (!b) {
          setError('empty')
          return
        }
        setBriefing(b)
        setGlossary(b.glossary ?? {})
      } catch (e) {
        if (!cancelled) setError(String(e))
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [date])

  const dict = t(lang)

  // 실적(picks 성과 추적) 탭
  if (scope === 'picks') {
    return <PicksHistoryView />
  }

  if (error) {
    return (
      <p className="px-5 py-20 text-center" style={{ color: 'var(--text-secondary)' }}>
        {dict['error.fetch']}
      </p>
    )
  }

  if (!briefing) {
    return (
      <p className="px-5 py-20 text-center" style={{ color: 'var(--text-secondary)' }}>
        {dict.loading}
      </p>
    )
  }

  const hotIssues = briefing.tabs.economy.hotIssues
  const issues = hotIssues
    ? scope === 'foreign'
      ? hotIssues.foreign
      : hotIssues.domestic
    : []

  if (issues.length === 0) {
    return (
      <div className="px-6 py-20 text-center" style={{ lineHeight: 1.7 }}>
        <p style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
          오늘은 강한 촉매가 있는 종목이 없어요
        </p>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
          약한 신호로 억지로 채우기보다 비워뒀어요. 확실한 게 생기면 바로 보여드릴게요.
        </p>
      </div>
    )
  }

  return (
    <div>
      <HotIssuesCard issues={issues} scope={scope} />
    </div>
  )
}

export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <HomeInner />
    </Suspense>
  )
}
