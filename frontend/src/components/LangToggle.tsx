'use client'

import { useEffect, useState } from 'react'
import { getStoredLang, storeLang, type Lang } from '@/lib/i18n'

export function LangToggle() {
  const [lang, setLang] = useState<Lang>('ko')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setLang(getStoredLang())
    setMounted(true)
  }, [])

  function toggle() {
    const next: Lang = lang === 'ko' ? 'en' : 'ko'
    setLang(next)
    storeLang(next)
    // 현재는 정적 로드. 새로고침으로 사전 전환.
    location.reload()
  }

  if (!mounted) return <div style={{ width: 56, height: 36 }} />

  return (
    <button
      onClick={toggle}
      className="px-2 text-xs font-bold tracking-tight"
      style={{ color: 'var(--text-secondary)' }}
    >
      {lang === 'ko' ? 'KO · EN' : 'EN · KO'}
    </button>
  )
}
