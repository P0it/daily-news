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
    location.reload()
  }

  if (!mounted) return <div style={{ width: 36, height: 36 }} />

  return (
    <button
      onClick={toggle}
      aria-label={`Language: ${lang.toUpperCase()}. Switch to ${
        lang === 'ko' ? 'English' : '한국어'
      }.`}
      title={`${lang.toUpperCase()} → ${lang === 'ko' ? 'EN' : 'KO'}`}
      className="flex items-center justify-center rounded-full"
      style={{
        width: 36,
        height: 36,
        color: 'var(--text-secondary)',
      }}
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <circle cx="12" cy="12" r="10" />
        <path d="M2 12h20" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    </button>
  )
}
