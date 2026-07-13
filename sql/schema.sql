DROP TABLE IF EXISTS chunks;

CREATE TABLE chunks (
    chunk_id       TEXT PRIMARY KEY,
    file_id        TEXT NOT NULL,      -- was INTEGER; your IDs are slugs
    meeting_date   DATE,
    meeting_title  TEXT,
    doc_label      TEXT,
    page_start     INTEGER,
    page_end       INTEGER,
    text           TEXT NOT NULL,
    embedding      vector(384)
);
