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
