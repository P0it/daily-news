import type { Metadata } from 'next'
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
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
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
        <main className="mx-auto" style={{ maxWidth: 'var(--container-briefing)' }}>
          {children}
        </main>
      </body>
    </html>
  )
}
