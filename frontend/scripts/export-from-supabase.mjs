// 배포 빌드시 Supabase(원본)에서 브리핑·성과 데이터를 끌어와 public/ 에 정적
// 파일로 내보낸다. 여러 머신이 DB에 생성·갱신하고, 배포 서버는 빌드할 때마다
// 여기서 최신본을 복원하므로 git 커밋이나 특정 머신에 의존하지 않는다.
//
// 환경변수(둘 다 필요):
//   SUPABASE_URL (없으면 NEXT_PUBLIC_SUPABASE_URL)
//   SUPABASE_SERVICE_KEY (없으면 SUPABASE_ANON_KEY / NEXT_PUBLIC_SUPABASE_ANON_KEY)
// → Vercel 에 이미 NEXT_PUBLIC_SUPABASE_URL·NEXT_PUBLIC_SUPABASE_ANON_KEY 가 있으면
//   그대로 인식한다. anon key 는 RLS public_read 정책으로 읽기만 허용되므로 충분.
// 로컬 dev 편의를 위해 저장소 루트 .env 도 폴백으로 읽는다.
// 자격증명이 없거나 조회가 실패하면 경고만 남기고 종료(기존 파일 유지) — 빌드/dev
// 를 막지 않는다.

import { mkdir, writeFile, readFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = join(__dirname, '..')
const REPO_ROOT = join(FRONTEND_ROOT, '..')
const PUBLIC_DIR = join(FRONTEND_ROOT, 'public')
const BRIEFINGS_DIR = join(PUBLIC_DIR, 'briefings')
const KEEP_DAYS = 30

/** 저장소 루트 .env 를 파싱해 process.env 에 없으면 채운다(로컬 dev 폴백). */
async function loadRootEnv() {
  const envPath = join(REPO_ROOT, '.env')
  if (!existsSync(envPath)) return
  const text = await readFile(envPath, 'utf-8')
  for (const line of text.split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/)
    if (!m) continue
    const key = m[1]
    let val = m[2].trim()
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1)
    }
    // dotenvx 로 암호화된 값(encrypted:...)은 복호화 없이 못 쓰므로 무시한다.
    // 그래야 Vercel 빌드에서 커밋된 암호화 .env 가 NEXT_PUBLIC_* 를 가리지 않는다.
    // (실제 값은 Vercel 환경변수 또는 `dotenvx run` 주입으로 process.env 에 들어온다.)
    if (val.startsWith('encrypted:')) continue
    if (process.env[key] === undefined) process.env[key] = val
  }
}

async function main() {
  await loadRootEnv()

  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
  const key =
    process.env.SUPABASE_SERVICE_KEY ||
    process.env.SUPABASE_ANON_KEY ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!url || !key) {
    console.warn('[export] SUPABASE_URL/KEY 없음 → 기존 정적 파일 유지(스킵).')
    return
  }

  const rest = async (path) => {
    const res = await fetch(`${url}/rest/v1/${path}`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
    })
    if (!res.ok) throw new Error(`Supabase ${path} → ${res.status} ${await res.text()}`)
    return res.json()
  }

  await mkdir(BRIEFINGS_DIR, { recursive: true })

  // 1. briefings 최근 N일 → 날짜별 파일 + index.json
  const rows = await rest(`briefings?select=date,data&order=date.desc&limit=${KEEP_DAYS}`)
  const dates = []
  for (const row of rows) {
    if (!row.date || typeof row.data !== 'object' || row.data === null) continue
    await writeFile(
      join(BRIEFINGS_DIR, `${row.date}.json`),
      JSON.stringify(row.data, null, 2),
    )
    dates.push(row.date)
  }
  dates.sort().reverse()
  await writeFile(
    join(BRIEFINGS_DIR, 'index.json'),
    JSON.stringify({ dates }, null, 2),
  )

  // 2. picks_history(단일 행) → picks_history.json
  const ph = await rest('picks_history?select=data&id=eq.current&limit=1')
  const phData = ph[0]?.data ?? { updatedAt: '', records: [] }
  await writeFile(
    join(PUBLIC_DIR, 'picks_history.json'),
    JSON.stringify(phData, null, 2),
  )

  // 3. discovery_screens(단일 행) → discovery.json (펀더멘털 발굴 스냅샷)
  let discCount = 0
  try {
    const ds = await rest('discovery_screens?select=data&id=eq.current&limit=1')
    const dsData = ds[0]?.data ?? { generatedAt: '', us: [], kospi: [] }
    discCount = (dsData.us || []).length + (dsData.kospi || []).length
    await writeFile(
      join(PUBLIC_DIR, 'discovery.json'),
      JSON.stringify(dsData, null, 2),
    )
  } catch (e) {
    // 테이블 미적용 등 — 기존 discovery.json 유지(있으면)
    console.warn(`[export] discovery 스킵: ${e.message}`)
  }

  console.log(
    `[export] briefings ${dates.length}일치, picks ${(phData.records || []).length}건, ` +
      `발굴 ${discCount}종목 복원`,
  )
}

main().catch((err) => {
  // 빌드/dev 를 막지 않도록 비치명적으로 처리(기존 파일 유지).
  console.warn(`[export] 실패(기존 파일 유지): ${err.message}`)
})
