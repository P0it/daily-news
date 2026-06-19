-- Supabase 스키마 초기화 SQL
-- Supabase 대시보드 > SQL Editor 에서 실행

CREATE TABLE IF NOT EXISTS seen (
    source  TEXT NOT NULL,
    ext_id  TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    PRIMARY KEY (source, ext_id)
);
CREATE INDEX IF NOT EXISTS idx_seen_time ON seen(seen_at);

CREATE TABLE IF NOT EXISTS llm_cache (
    content_hash TEXT PRIMARY KEY,
    task         TEXT NOT NULL,
    output       TEXT NOT NULL,
    model        TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS glossary (
    term_id          TEXT NOT NULL,
    lang             TEXT NOT NULL DEFAULT 'ko',
    short_label      TEXT NOT NULL,
    explanation      TEXT NOT NULL,
    signal_direction TEXT,
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (term_id, lang)
);

CREATE TABLE IF NOT EXISTS tickers (
    stock_code TEXT PRIMARY KEY,
    corp_code  TEXT NOT NULL,
    corp_name  TEXT NOT NULL,
    market     TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tickers_corp ON tickers(corp_code);

CREATE TABLE IF NOT EXISTS themes (
    theme_id    TEXT PRIMARY KEY,
    name_ko     TEXT NOT NULL,
    description TEXT,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS value_layers (
    layer_id    SERIAL PRIMARY KEY,
    theme_id    TEXT NOT NULL REFERENCES themes(theme_id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    updated_at  TEXT NOT NULL,
    UNIQUE (theme_id, name)
);
CREATE INDEX IF NOT EXISTS idx_layers_theme ON value_layers(theme_id);

CREATE TABLE IF NOT EXISTS companies_in_layer (
    layer_id     INTEGER NOT NULL REFERENCES value_layers(layer_id) ON DELETE CASCADE,
    ticker       TEXT NOT NULL,
    company_name TEXT NOT NULL,
    positioning  TEXT,
    verified     INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (layer_id, ticker)
);
CREATE INDEX IF NOT EXISTS idx_companies_ticker ON companies_in_layer(ticker);

CREATE TABLE IF NOT EXISTS embeddings (
    doc_id        TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    content       TEXT NOT NULL,
    vector        BYTEA NOT NULL,
    dim           INTEGER NOT NULL,
    metadata_json TEXT,
    indexed_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_embeddings_source ON embeddings(source);
CREATE INDEX IF NOT EXISTS idx_embeddings_indexed_at ON embeddings(indexed_at);

CREATE TABLE IF NOT EXISTS rag_queries (
    id           SERIAL PRIMARY KEY,
    query        TEXT NOT NULL,
    answer       TEXT,
    sources_json TEXT,
    model        TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rag_queries_created ON rag_queries(created_at);

CREATE TABLE IF NOT EXISTS briefings (
    date       TEXT PRIMARY KEY,
    data       JSONB NOT NULL,
    created_at TEXT NOT NULL
);

-- briefings 공개 읽기 허용 (anon key로 프론트엔드 접근)
ALTER TABLE briefings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public_read" ON briefings FOR SELECT USING (true);

-- picks_history: 추천 종목 성과 전체를 단일 행(id='current') JSON 으로 보관.
-- 여러 생성 머신이 같은 행을 upsert 하고, 배포 빌드가 여기서 읽어 복원한다.
CREATE TABLE IF NOT EXISTS picks_history (
    id         TEXT PRIMARY KEY,
    data       JSONB NOT NULL,
    updated_at TEXT NOT NULL
);
ALTER TABLE picks_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public_read" ON picks_history FOR SELECT USING (true);

-- pick_outcomes: 추천 픽 영구 원장 (재학습 데이터의 원천).
-- picks_history(실적 탭용 30일 실시간 수익률)와 달리 폐기하지 않고 픽 1건=1행으로 보관한다.
-- 추천 시점 예측 방향·촉매·근거를 스냅샷하고, T+1/T+5/T+20 종가로 수익률·적중을 채점한다.
-- 행 단위 컬럼이라 촉매 유형별 적중률 집계(SQL/파이썬)가 쉽다.
CREATE TABLE IF NOT EXISTS pick_outcomes (
    id             TEXT PRIMARY KEY,   -- {rec_date}-{scope}-{ticker}
    rec_date       TEXT NOT NULL,      -- 추천일 YYYY-MM-DD
    ticker         TEXT NOT NULL,
    name           TEXT,
    scope          TEXT NOT NULL,      -- domestic | foreign
    direction      TEXT,               -- 예측 방향: positive | negative | mixed
    signal         TEXT,               -- 촉매 (issue.signal)
    theme          TEXT,               -- issue.asset
    rationale      TEXT,               -- pick.description
    consensus_risk TEXT,               -- low | medium | high
    verify_status  TEXT,               -- ok | review
    is_filer       INTEGER,            -- 공시 주체 여부 (1/0)
    currency       TEXT,               -- KRW | USD
    price_at_rec   REAL,               -- 진입 기준가 = 추천 직전 거래일 종가
    price_1d       REAL,
    price_5d       REAL,
    price_20d      REAL,
    ret_1d         REAL,               -- 기준가 대비 % 절대수익률
    ret_5d         REAL,
    ret_20d        REAL,
    bench_ret_1d   REAL,               -- 같은 구간 벤치마크 지수 % 수익률
    bench_ret_5d   REAL,
    bench_ret_20d  REAL,
    alpha_1d       REAL,               -- 초과수익 = ret - bench_ret (핵심 채점 기준)
    alpha_5d       REAL,
    alpha_20d      REAL,
    benchmark      TEXT,               -- 사용한 벤치마크 심볼 (^KS11 | ^KQ11 | ^GSPC)
    hit_1d         INTEGER,            -- 알파 기준 1 적중 / 0 실패 / null 보류·mixed·데드밴드
    hit_5d         INTEGER,
    hit_20d        INTEGER,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pick_outcomes_date ON pick_outcomes(rec_date);
CREATE INDEX IF NOT EXISTS idx_pick_outcomes_pending ON pick_outcomes(price_20d);
ALTER TABLE pick_outcomes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public_read" ON pick_outcomes FOR SELECT USING (true);
