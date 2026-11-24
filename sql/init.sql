-- Medallion layers. Executed once by the postgres image on first start.

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS meta;

-- BRONZE: raw data exactly as the API returns it. Everything is TEXT on purpose:
-- no validation and no cleaning happens here.
CREATE TABLE IF NOT EXISTS bronze.precios_raw (
    productos      TEXT,
    mercados       TEXT,
    precio_m_nimo  TEXT,
    precio_m_ximo  TEXT,
    precio_medio   TEXT,
    fecha_inicial  TEXT,
    fecha_final    TEXT,
    categoria      TEXT,
    ciudad         TEXT,
    _batch_id      TEXT        NOT NULL,
    _source_url    TEXT        NOT NULL,
    _ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bronze_batch ON bronze.precios_raw (_batch_id);

-- SILVER: typed, normalized and deduplicated. Only rows from a batch that
-- passed the quality gate are loaded here.
CREATE TABLE IF NOT EXISTS silver.precios (
    producto       TEXT           NOT NULL,
    mercado        TEXT           NOT NULL,
    categoria      TEXT           NOT NULL,
    ciudad         TEXT           NOT NULL,
    precio_minimo  NUMERIC(12, 2) NOT NULL,
    precio_maximo  NUMERIC(12, 2) NOT NULL,
    precio_medio   NUMERIC(12, 2) NOT NULL,
    fecha_inicial  DATE           NOT NULL,
    fecha_final    DATE           NOT NULL,
    _batch_id      TEXT           NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_silver_lookup
    ON silver.precios (producto, ciudad, fecha_inicial);

-- GOLD: aggregates ready for decisions. The dashboard reads only from here.
CREATE TABLE IF NOT EXISTS gold.precio_mensual (
    producto         TEXT           NOT NULL,
    categoria        TEXT           NOT NULL,
    ciudad           TEXT           NOT NULL,
    mes              DATE           NOT NULL,
    precio_promedio  NUMERIC(12, 2) NOT NULL,
    observaciones    INTEGER        NOT NULL,
    PRIMARY KEY (producto, ciudad, mes)
);

CREATE TABLE IF NOT EXISTS gold.variacion_mensual (
    producto         TEXT           NOT NULL,
    ciudad           TEXT           NOT NULL,
    mes              DATE           NOT NULL,
    precio_promedio  NUMERIC(12, 2) NOT NULL,
    precio_anterior  NUMERIC(12, 2),
    variacion_pct    NUMERIC(10, 2),
    PRIMARY KEY (producto, ciudad, mes)
);

-- META: audit trail of every quality gate run, shown on the dashboard.
CREATE TABLE IF NOT EXISTS meta.quality_runs (
    id                BIGSERIAL PRIMARY KEY,
    batch_id          TEXT        NOT NULL,
    passed            BOOLEAN     NOT NULL,
    expectations_run  INTEGER     NOT NULL,
    expectations_failed INTEGER   NOT NULL,
    failed_details    JSONB,
    rows_checked      INTEGER     NOT NULL,
    executed_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
