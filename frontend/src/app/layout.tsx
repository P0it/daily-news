import type { Metadata } from 'next'
import { AppShell } from '@/components/AppShell'
import { InstallPrompt } from '@/components/InstallPrompt'
import { ServiceWorkerRegister } from '@/components/ServiceWorkerRegister'
import './globals.css'

export const metadata: Metadata = {
  title: '데일리 브리핑',
  description: '매일 아침 공시·뉴스 브리핑',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    title: '브리핑',
    statusBarStyle: 'default',
  },
  icons: {
    icon: [
      { url: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: '/icons/apple-touch-icon.png',
  },
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
        <AppShell>{children}</AppShell>
        <InstallPrompt />
        <ServiceWorkerRegister />
      </body>
    </html>
  )
}
