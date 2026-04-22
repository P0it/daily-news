'use client'

import { useEffect } from 'react'

export function ServiceWorkerRegister() {
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // 등록 실패 (HTTPS 아님 등) 는 조용히 무시
      })
    }
  }, [])
  return null
}
