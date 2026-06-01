export type Scope = 'domestic' | 'foreign'

export type Tab = 'ai' | 'current' | 'economy'

const TABS_SET: ReadonlySet<string> = new Set(['ai', 'current', 'economy'])
const DEFAULT_TAB: Tab = 'ai'

export function parseTabFromSearch(search: URLSearchParams | string): Tab {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search
  const v = p.get('tab')
  return TABS_SET.has(v ?? '') ? (v as Tab) : DEFAULT_TAB
}

export function tabHref(tab: Tab, date?: string | null): string {
  const p = new URLSearchParams()
  if (date) p.set('date', date)
  if (tab !== DEFAULT_TAB) p.set('tab', tab)
  return p.size > 0 ? `/?${p.toString()}` : '/'
}

const SCOPES_SET: ReadonlySet<string> = new Set(['domestic', 'foreign'])
const DEFAULT_SCOPE: Scope = 'domestic'

export function parseScopeFromSearch(search: URLSearchParams | string): Scope {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search
  const v = p.get('scope')
  return SCOPES_SET.has(v ?? '') ? (v as Scope) : DEFAULT_SCOPE
}

export function parseDateFromSearch(search: URLSearchParams | string): string | null {
  const p = typeof search === 'string' ? new URLSearchParams(search) : search
  const v = p.get('date')
  return v && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null
}

export function scopeHref(scope: Scope, date?: string | null): string {
  const p = new URLSearchParams()
  if (date) p.set('date', date)
  if (scope !== DEFAULT_SCOPE) p.set('scope', scope)
  return p.size > 0 ? `/?${p.toString()}` : '/'
}
