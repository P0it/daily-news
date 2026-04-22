export type Theme = 'light' | 'dark'
const KEY = 'news-briefing:theme'

export function getStoredTheme(): Theme | null {
  if (typeof window === 'undefined') return null
  const v = localStorage.getItem(KEY)
  return v === 'light' || v === 'dark' ? v : null
}

export function storeTheme(t: Theme) {
  localStorage.setItem(KEY, t)
}

export function systemPrefersDark(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function applyTheme(t: Theme) {
  const root = document.documentElement
  if (t === 'dark') root.classList.add('dark')
  else root.classList.remove('dark')
}

export function resolveInitialTheme(): Theme {
  const stored = getStoredTheme()
  if (stored) return stored
  return systemPrefersDark() ? 'dark' : 'light'
}
