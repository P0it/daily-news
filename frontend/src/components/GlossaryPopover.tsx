'use client'

import { useEffect, useState } from 'react'
import { getGlossary } from '@/lib/glossaryStore'
import type { GlossaryEntry } from '@/lib/types'

const ACK_KEY = 'news-briefing:glossary-ack'

function isAcknowledged(termId: string): boolean {
  if (typeof window === 'undefined') return false
  try {
    const raw = localStorage.getItem(ACK_KEY)
    if (!raw) return false
    const list: string[] = JSON.parse(raw)
    return list.includes(termId)
  } catch {
    return false
  }
}

function acknowledge(termId: string) {
  try {
    const raw = localStorage.getItem(ACK_KEY)
    const list: string[] = raw ? JSON.parse(raw) : []
    if (!list.includes(termId)) list.push(termId)
    localStorage.setItem(ACK_KEY, JSON.stringify(list))
  } catch {
    // 무시
  }
}

export function GlossaryPopover({
  termId,
  dict,
  defaultOpen = false,
}: {
  termId: string
  dict: import('@/lib/i18n/ko').Dict
  defaultOpen?: boolean
}) {
  const [entry, setEntry] = useState<GlossaryEntry | null>(null)
  const [open, setOpen] = useState(defaultOpen)

  useEffect(() => {
    setEntry(getGlossary(termId))
    if (!defaultOpen && isAcknowledged(termId)) {
      setOpen(false)
    }
  }, [termId, defaultOpen])

  if (!entry) return null

  const heading = dict['glossary.heading'](entry.shortLabel)

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full text-left"
        style={{
          marginTop: 16,
          background: 'var(--bg-inset)',
          borderRadius: 'var(--radius-btn)',
          padding: '14px 16px',
          fontSize: 13,
          fontWeight: 600,
          color: 'var(--text-tertiary)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span aria-hidden>💡</span>
        <span>{heading}</span>
        <span className="ml-auto" style={{ fontSize: 11, fontWeight: 700 }}>
          +
        </span>
      </button>
    )
  }

  return (
    <div
      style={{
        marginTop: 16,
        background: 'var(--bg-inset)',
        borderRadius: 'var(--radius-btn)',
        padding: '16px 18px',
      }}
    >
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: 'var(--text-tertiary)',
          letterSpacing: '-0.01em',
          marginBottom: 8,
        }}
      >
        {heading}
      </div>
      <div
        style={{
          fontSize: 14,
          lineHeight: 1.65,
          color: 'var(--text-secondary)',
        }}
      >
        {entry.explanation}
      </div>
      <button
        type="button"
        onClick={() => {
          acknowledge(termId)
          setOpen(false)
        }}
        className="block ml-auto"
        style={{
          marginTop: 12,
          fontSize: 12,
          fontWeight: 700,
          color: 'var(--text-secondary)',
        }}
      >
        {dict['glossary.acknowledge']}
      </button>
    </div>
  )
}
