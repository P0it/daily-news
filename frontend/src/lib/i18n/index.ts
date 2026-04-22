import { ko, type Dict } from './ko'
import { en } from './en'

export type Lang = 'ko' | 'en'
const KEY = 'news-briefing:lang'

const DICT: Record<Lang, Dict> = { ko, en }

export function getStoredLang(): Lang {
  if (typeof window === 'undefined') return 'ko'
  const v = localStorage.getItem(KEY)
  if (v === 'ko' || v === 'en') return v
  const browser =
    typeof navigator !== 'undefined' ? navigator.language?.slice(0, 2) : 'ko'
  return browser === 'en' ? 'en' : 'ko'
}

export function storeLang(lang: Lang) {
  localStorage.setItem(KEY, lang)
}

export function t(lang: Lang): Dict {
  return DICT[lang]
}
