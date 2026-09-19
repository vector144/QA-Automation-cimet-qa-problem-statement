-- CIMET QA Automation — SQLite Schema
-- Executed on startup via init_db()

CREATE TABLE IF NOT EXISTS leads (
    id              TEXT PRIMARY KEY,
    retailer_id     TEXT NOT NULL,
    retailer_name   TEXT,
    agent_id        TEXT,
    agent_name      TEXT,
    call_date       TEXT NOT NULL,
    crm_fields      TEXT NOT NULL DEFAULT '{}',
    rate_card       TEXT,
    recording_url   TEXT,
    gate_status     TEXT NOT NULL DEFAULT 'PENDING',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transcripts (
    lead_id         TEXT PRIMARY KEY,
    turns           TEXT NOT NULL,
    full_text       TEXT,
    redacted        INTEGER NOT NULL DEFAULT 0,
    source          TEXT NOT NULL DEFAULT 'provided',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS score_runs (
    id                      TEXT PRIMARY KEY,
    lead_id                 TEXT NOT NULL,
    check_library_id        TEXT NOT NULL,
    check_library_version   TEXT NOT NULL,
    overall_status          TEXT,
    gate_decision           TEXT,
    score                   REAL DEFAULT 100.0,
    human_sampled           INTEGER NOT NULL DEFAULT 0,
    run_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    human_override          TEXT
);

CREATE TABLE IF NOT EXISTS check_results (
    id                      TEXT PRIMARY KEY,
    run_id                  TEXT NOT NULL,
    check_id                TEXT NOT NULL,
    check_name              TEXT NOT NULL,
    check_type              TEXT NOT NULL,
    is_critical             INTEGER NOT NULL,
    blocks_sale             INTEGER NOT NULL,
    status                  TEXT NOT NULL,
    confidence              REAL,
    agent_said              TEXT,
    expected_value          TEXT,
    transcript_turn         INTEGER,
    transcript_line         TEXT,
    timestamp_ms            INTEGER,
    reason                  TEXT NOT NULL,
    check_library_version   TEXT
);

CREATE TABLE IF NOT EXISTS repeat_offences (
    id          TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    check_id    TEXT NOT NULL,
    check_name  TEXT NOT NULL,
    fail_date   TEXT NOT NULL,
    lead_id     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_overrides (
    id              TEXT PRIMARY KEY,
    lead_id         TEXT NOT NULL,
    check_id        TEXT,
    reviewer_id     TEXT NOT NULL,
    reviewer_name   TEXT,
    previous_status TEXT NOT NULL,
    new_status      TEXT NOT NULL,
    justification   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
