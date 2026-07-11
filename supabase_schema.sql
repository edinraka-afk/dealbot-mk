-- DealBot MK v2 — Supabase schema
-- Run this once in the Supabase SQL editor to initialise the project.

CREATE TABLE IF NOT EXISTS listings (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,          -- 'reklama5' | 'pazar3'
    listing_id    TEXT        NOT NULL,
    title         TEXT,
    make          TEXT,
    model         TEXT,
    price_eur     INTEGER,
    year          INTEGER,
    mileage       INTEGER,
    fuel_type     TEXT,
    transmission  TEXT,
    engine_size   TEXT,
    location      TEXT,
    listing_url   TEXT,
    date_posted   TEXT,
    is_deal       BOOLEAN     DEFAULT FALSE,
    deal_score    FLOAT,
    alerted_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source, listing_id)
);

CREATE TABLE IF NOT EXISTS crawl_checkpoints (
    id                  BIGSERIAL PRIMARY KEY,
    source              TEXT    NOT NULL,
    crawl_type          TEXT    NOT NULL,        -- 'full' | 'incremental'
    price_range_start   INTEGER NOT NULL DEFAULT 0,
    price_range_end     INTEGER,                 -- NULL means no upper limit
    current_page        INTEGER NOT NULL DEFAULT 1,
    status              TEXT    NOT NULL DEFAULT 'in_progress', -- 'in_progress' | 'done'
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source, crawl_type, price_range_start, price_range_end)
);

-- Allow the anon key (used by the bot) full access.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE listings            TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE crawl_checkpoints   TO anon;
GRANT USAGE, SELECT ON SEQUENCE listings_id_seq                   TO anon;
GRANT USAGE, SELECT ON SEQUENCE crawl_checkpoints_id_seq          TO anon;
