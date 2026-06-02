import type { Metadata } from 'next'
import { AppShell } from '@/components/AppShell'
import './globals.css'

export const metadata: Metadata = {
  title: '데일리 브리핑',
  description: '매일 아침 공시·뉴스 브리핑',
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <link
          rel="stylesheet"
          href="/fonts/tps-main.css"
        />
        <meta
          name="theme-color"
          content="#F9FAFB"
          media="(prefers-color-scheme: light)"
        />
        <meta
          name="theme-color"
          content="#191F28"
          media="(prefers-color-scheme: dark)"
        />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  )
}
