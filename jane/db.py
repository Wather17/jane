"""SQLite connection and schema management for Jane."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("data/jane.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS words (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma           TEXT NOT NULL UNIQUE,
    in_oxford       INTEGER NOT NULL DEFAULT 0,
    in_ngsl         INTEGER NOT NULL DEFAULT 0,
    cefr_level      TEXT,
    pos             TEXT,
    ngsl_rank       INTEGER,
    ngsl_freq       REAL,
    tier            INTEGER NOT NULL,
    priority_score  REAL NOT NULL,
    batch_number    INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cards (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    card_uid          TEXT NOT NULL UNIQUE,
    word_id           INTEGER NOT NULL,
    sense_index       INTEGER NOT NULL DEFAULT 1,
    pos               TEXT,
    difficulty        TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    sentence_display  TEXT NOT NULL,
    sentence_audio    TEXT NOT NULL,
    sentence_pt       TEXT NOT NULL,
    word_meaning_pt   TEXT NOT NULL,
    notes             TEXT DEFAULT '',
    char_count        INTEGER NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    exported_at       TEXT,
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,
    UNIQUE (word_id, sense_index)
);

CREATE INDEX IF NOT EXISTS idx_words_batch_status ON words(batch_number, status);
CREATE INDEX IF NOT EXISTS idx_words_priority ON words(priority_score);
CREATE INDEX IF NOT EXISTS idx_cards_word_id ON cards(word_id);
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enabled and Row factory."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they do not exist, applying idempotent migrations."""
    conn.executescript(SCHEMA_SQL)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(cards)").fetchall()}
    if "updated_at" not in cols:
        conn.execute("ALTER TABLE cards ADD COLUMN updated_at TEXT")
        conn.execute("UPDATE cards SET updated_at = COALESCE(updated_at, created_at)")
    if "exported_at" not in cols:
        conn.execute("ALTER TABLE cards ADD COLUMN exported_at TEXT")
        conn.execute(
            """
            UPDATE cards
            SET exported_at = created_at
            WHERE exported_at IS NULL
              AND word_id IN (SELECT id FROM words WHERE status IN ('exported', 'mastered'))
            """
        )
    conn.commit()
