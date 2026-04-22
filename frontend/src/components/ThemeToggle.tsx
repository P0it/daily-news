'use client'

import { useEffect, useState } from 'react'
import { applyTheme, resolveInitialTheme, storeTheme, type Theme } from '@/lib/theme'

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>('light')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const initial = resolveInitialTheme()
    setTheme(initial)
    applyTheme(initial)
    setMounted(true)
  }, [])

  function toggle() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    storeTheme(next)
    applyTheme(next)
  }

  if (!mounted) return <div style={{ width: 36, height: 36 }} />

  return (
    <button
      onClick={toggle}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      className="p-2 rounded-full text-[15px]"
      style={{ color: 'var(--text-secondary)' }}
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
