'use client'

import { useEffect, useState } from 'react'
import { getStoredLang, t } from '@/lib/i18n'

const DISMISSED_KEY = 'news-briefing:install-dismissed-at'
const COOLDOWN_DAYS = 7

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null)
  const [visible, setVisible] = useState(false)
  const dict = t(getStoredLang())

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault()
      const dismissedAt = Number(localStorage.getItem(DISMISSED_KEY) || 0)
      const cooldown = dismissedAt + COOLDOWN_DAYS * 24 * 3600 * 1000
      if (Date.now() < cooldown) return
      setDeferred(e as BeforeInstallPromptEvent)
      setVisible(true)
    }
    window.addEventListener('beforeinstallprompt', handler as EventListener)
    return () => {
      window.removeEventListener('beforeinstallprompt', handler as EventListener)
    }
  }, [])

  if (!visible) return null

  async function install() {
    if (!deferred) return
    await deferred.prompt()
    await deferred.userChoice
    setVisible(false)
  }

  function dismiss() {
    localStorage.setItem(DISMISSED_KEY, String(Date.now()))
    setVisible(false)
  }

  return (
    <div
      className="fixed bottom-4 inset-x-4 z-50 flex items-center gap-3"
      style={{
        background: '#1E2127',
        color: '#F9FAFB',
        borderRadius: 'var(--radius-card)',
        padding: '18px 20px',
        maxWidth: 'var(--container-briefing)',
        marginLeft: 'auto',
        marginRight: 'auto',
      }}
    >
      <div className="flex-1">
        <div style={{ fontSize: 15, fontWeight: 700 }}>{dict['install.title']}</div>
        <div style={{ fontSize: 13, color: '#B0B8C1', marginTop: 2 }}>
          {dict['install.subtitle']}
        </div>
      </div>
      <button
        onClick={dismiss}
        style={{ fontSize: 12, color: '#8B95A1', padding: '4px 8px' }}
      >
        {dict['install.dismiss']}
      </button>
      <button
        onClick={install}
        style={{
          background: '#F9FAFB',
          color: '#191F28',
          borderRadius: 'var(--radius-btn)',
          padding: '10px 16px',
          fontSize: 13,
          fontWeight: 700,
        }}
      >
        {dict['install.cta']}
      </button>
    </div>
  )
}
