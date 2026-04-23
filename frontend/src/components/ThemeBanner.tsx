'use client'

import type { ThemeBanner as ThemeBannerType } from '@/lib/types'

export function ThemeBanner({ banner }: { banner: ThemeBannerType }) {
  if (banner.trendingThemes.length === 0) return null
  return (
    <section
      className="mx-4 mb-2.5"
      style={{
        background: 'var(--bg-card)',
        borderRadius: 'var(--radius-card)',
        padding: '20px 22px',
      }}
    >
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          color: 'var(--text-tertiary)',
          letterSpacing: '-0.01em',
          marginBottom: 10,
        }}
      >
        이번 주 주목 테마
      </div>
      <div className="flex flex-wrap gap-2" style={{ marginBottom: 14 }}>
        {banner.trendingThemes.map((theme) => (
          <span
            key={theme}
            style={{
              padding: '6px 10px',
              fontSize: 13,
              fontWeight: 700,
              color: 'var(--text-primary)',
              background: 'var(--bg-inset)',
              borderRadius: 999,
            }}
          >
            {theme}
          </span>
        ))}
      </div>
      {banner.reportUrl && (
        <a
          href={banner.reportUrl}
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: 'var(--text-primary)',
          }}
        >
          주간 리포트 보기 →
        </a>
      )}
    </section>
  )
}
