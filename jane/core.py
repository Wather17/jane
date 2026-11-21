"""Core operations: status, next, save, export, master."""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

HTML_TAG_RE = re.compile(r"<[^>]+>")
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
TSV_COLUMNS = [
    "Card_UID",
    "Word",
    "Sentence_Display",
    "Sentence_Audio",
    "Sentence_PT",
    "Word_Meaning_PT",
    "Difficulty",
    "Batch",
    "Notes",
]


def _clean_tsv_cell(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def get_status(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return summary counts across the database and per batch."""
    totals = dict(
        conn.execute(
            """
            SELECT
                COUNT(*) AS words_total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'generated' THEN 1 ELSE 0 END) AS generated,
                SUM(CASE WHEN status = 'exported' THEN 1 ELSE 0 END) AS exported,
                SUM(CASE WHEN status = 'mastered' THEN 1 ELSE 0 END) AS mastered
            FROM words
            """
        ).fetchone()
    )
    card_stats = dict(
        conn.execute(
            "SELECT COUNT(*) AS cards_total, COALESCE(SUM(char_count), 0) AS total_chars FROM cards"
        ).fetchone()
    )
    batches = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                w.batch_number,
                COUNT(DISTINCT w.id) AS words,
                SUM(CASE WHEN w.status = 'pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN w.status = 'generated' THEN 1 ELSE 0 END) AS generated,
                SUM(CASE WHEN w.status = 'exported' THEN 1 ELSE 0 END) AS exported,
                SUM(CASE WHEN w.status = 'mastered' THEN 1 ELSE 0 END) AS mastered,
                COALESCE(SUM(c.char_count), 0) AS chars
            FROM words w
            LEFT JOIN cards c ON c.word_id = w.id
            GROUP BY w.batch_number
            ORDER BY w.batch_number
            """
        ).fetchall()
    ]
    return {"totals": totals, "cards": card_stats, "batches": batches}


def get_next_batch(
    conn: sqlite3.Connection,
    batch_number: int = 1,
    limit: int = 20,
    include_known: bool = True,
) -> dict[str, Any]:
    """Fetch next pending words in a batch plus optional known words for i+1 context."""
    pending_rows = conn.execute(
        """
        SELECT id, lemma, cefr_level, pos, ngsl_rank, tier
        FROM words
        WHERE batch_number = ? AND status = 'pending'
        ORDER BY priority_score ASC, id ASC
        LIMIT ?
        """,
        (batch_number, limit),
    ).fetchall()

    known_words: list[str] = []
    if include_known:
        known_rows = conn.execute(
            """
            SELECT lemma
            FROM words
            WHERE batch_number < ? OR status IN ('generated', 'exported', 'mastered')
            ORDER BY priority_score ASC
            """,
            (batch_number,),
        ).fetchall()
        known_words = [r["lemma"] for r in known_rows]

    return {
        "batch_number": batch_number,
        "pending_count": len(pending_rows),
        "pending_words": [dict(r) for r in pending_rows],
        "known_words": known_words,
    }


def validate_card_payload(item: dict[str, Any]) -> list[str]:
    """Validate a single card JSON object and return a list of error messages."""
    errors: list[str] = []
    required = ["lemma", "difficulty", "sentence_display", "sentence_audio", "sentence_pt", "word_meaning_pt"]
    for field in required:
        val = item.get(field)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"missing or empty '{field}'")

    if errors:
        return errors

    difficulty = item["difficulty"].strip().lower()
    if difficulty not in VALID_DIFFICULTIES:
        errors.append(f"invalid difficulty '{difficulty}' (expected easy|medium|hard)")

    s_audio = item["sentence_audio"].strip()
    s_disp = item["sentence_display"].strip()

    if "<" in s_audio or ">" in s_audio:
        errors.append("sentence_audio must not contain HTML tags")

    if "<b>" not in s_disp or "</b>" not in s_disp:
        errors.append("sentence_display must highlight the target word with <b>...</b>")

    stripped_disp = HTML_TAG_RE.sub("", s_disp).strip()
    if stripped_disp != s_audio:
        errors.append(f"sentence_display stripped ('{stripped_disp}') != sentence_audio ('{s_audio}')")

    word_count = len(s_audio.split())
    if word_count < 3 or word_count > 18:
        errors.append(f"sentence_audio word count ({word_count}) must be between 3 and 18")

    return errors


def save_cards(
    conn: sqlite3.Connection,
    items: list[dict[str, Any]],
    force: bool = False,
) -> dict[str, Any]:
    """Validate and persist generated cards into SQLite."""
    if not isinstance(items, list) or not items:
        raise ValueError("Input JSON must be a non-empty list of card objects")

    all_errors: list[str] = []
    saved = 0
    touched_word_ids: set[int] = set()

    for idx, item in enumerate(items):
        errs = validate_card_payload(item)
        if errs:
            all_errors.append(f"Item {idx} ({item.get('lemma', '?')}): " + "; ".join(errs))
            continue

        lemma = item["lemma"].strip().lower()
        word_row = conn.execute("SELECT id, pos, status FROM words WHERE lemma = ?", (lemma,)).fetchone()
        if word_row is None:
            all_errors.append(f"Item {idx} ({lemma}): lemma not found in words table")
            continue

        if word_row["status"] in ("exported", "mastered") and not force:
            all_errors.append(f"Item {idx} ({lemma}): word status is '{word_row['status']}' (use --force to overwrite)")
            continue

        sense_index = int(item.get("sense_index", 1))
        if sense_index < 1:
            all_errors.append(f"Item {idx} ({lemma}): sense_index must be >= 1")
            continue

        word_id = word_row["id"]
        card_uid = f"jane_{word_id:04d}_{sense_index:02d}"
        s_audio = _clean_tsv_cell(item["sentence_audio"])
        s_disp = _clean_tsv_cell(item["sentence_display"])
        s_pt = _clean_tsv_cell(item["sentence_pt"])
        meaning_pt = _clean_tsv_cell(item["word_meaning_pt"])
        notes = _clean_tsv_cell(str(item.get("notes") or ""))
        pos = _clean_tsv_cell(str(item.get("pos") or word_row["pos"] or "")) or None
        difficulty = item["difficulty"].strip().lower()
        char_count = len(s_audio)

        existing = conn.execute(
            "SELECT id FROM cards WHERE word_id = ? AND sense_index = ?",
            (word_id, sense_index),
        ).fetchone()

        if existing is not None:
            if not force:
                all_errors.append(f"Item {idx} ({lemma}, sense {sense_index}): card already exists (use --force)")
                continue
            conn.execute(
                """
                UPDATE cards SET
                    pos = ?, difficulty = ?, sentence_display = ?, sentence_audio = ?,
                    sentence_pt = ?, word_meaning_pt = ?, notes = ?, char_count = ?
                WHERE id = ?
                """,
                (pos, difficulty, s_disp, s_audio, s_pt, meaning_pt, notes, char_count, existing["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO cards (
                    card_uid, word_id, sense_index, pos, difficulty,
                    sentence_display, sentence_audio, sentence_pt,
                    word_meaning_pt, notes, char_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (card_uid, word_id, sense_index, pos, difficulty, s_disp, s_audio, s_pt, meaning_pt, notes, char_count),
            )

        touched_word_ids.add(word_id)
        saved += 1

    if all_errors:
        conn.rollback()
        raise ValueError("Validation failed:\n" + "\n".join(all_errors))

    for wid in touched_word_ids:
        conn.execute(
            "UPDATE words SET status = 'generated', updated_at = datetime('now') WHERE id = ? AND status = 'pending'",
            (wid,),
        )

    conn.commit()
    return {"saved": saved, "words_updated": len(touched_word_ids)}


def export_batch(
    conn: sqlite3.Connection,
    batch_number: int,
    out_path: Path | None = None,
    include_header: bool = True,
) -> dict[str, Any]:
    """Export all cards for a batch to a UTF-8 TSV file and estimate HyperTTS quota."""
    rows = conn.execute(
        """
        SELECT
            c.card_uid,
            w.lemma,
            c.sentence_display,
            c.sentence_audio,
            c.sentence_pt,
            c.word_meaning_pt,
            c.difficulty,
            w.batch_number,
            c.notes,
            c.char_count,
            w.id AS word_id
        FROM cards c
        JOIN words w ON w.id = c.word_id
        WHERE w.batch_number = ?
        ORDER BY w.priority_score ASC, c.sense_index ASC
        """,
        (batch_number,),
    ).fetchall()

    if not rows:
        raise ValueError(f"No generated cards found for batch {batch_number}")

    dest = out_path or Path(f"exports/batch_{batch_number:02d}.tsv")
    dest.parent.mkdir(parents=True, exist_ok=True)

    total_chars = 0
    word_ids: set[int] = set()

    with dest.open("w", encoding="utf-8", newline="") as f:
        if include_header:
            f.write("#separator:tab\n")
            f.write("#html:true\n")
            f.write("#notetype:Jane Vocab\n")
            f.write("#columns:" + "\t".join(TSV_COLUMNS) + "\n")
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        for r in rows:
            writer.writerow(
                [
                    r["card_uid"],
                    r["lemma"],
                    r["sentence_display"],
                    r["sentence_audio"],
                    r["sentence_pt"],
                    r["word_meaning_pt"],
                    r["difficulty"],
                    f"batch_{r['batch_number']:02d}",
                    r["notes"] or "",
                ]
            )
            total_chars += r["char_count"]
            word_ids.add(r["word_id"])

    for wid in word_ids:
        conn.execute(
            "UPDATE words SET status = 'exported', updated_at = datetime('now') WHERE id = ? AND status = 'generated'",
            (wid,),
        )
    conn.commit()

    return {
        "batch_number": batch_number,
        "cards_exported": len(rows),
        "output_path": str(dest),
        "total_chars": total_chars,
        "hypertts_estimate": {
            "1x_azure_google": total_chars,
            "2x_openai": total_chars * 2,
            "15x_elevenlabs": total_chars * 15,
        },
    }


def master_batch(conn: sqlite3.Connection, batch_number: int) -> dict[str, int]:
    """Mark all words in a batch as mastered."""
    cur = conn.execute(
        "UPDATE words SET status = 'mastered', updated_at = datetime('now') WHERE batch_number = ?",
        (batch_number,),
    )
    conn.commit()
    return {"batch_number": batch_number, "updated": cur.rowcount}


def add_words(
    conn: sqlite3.Connection,
    words: list[str],
    batch_number: int | None = None,
    batch_size: int = 120,
    pos: str | None = None,
    cefr_level: str | None = None,
) -> dict[str, Any]:
    """Add custom words or expressions to the words table with safe batch allocation."""
    if not words:
        raise ValueError("At least one word must be provided")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if batch_number is not None and batch_number <= 0:
        raise ValueError("batch_number must be positive")

    normalized_cefr: str | None = None
    if cefr_level is not None:
        normalized_cefr = cefr_level.strip().upper()
        if normalized_cefr not in VALID_CEFR_LEVELS:
            raise ValueError(
                f"Invalid CEFR level '{cefr_level}' (expected one of {', '.join(sorted(VALID_CEFR_LEVELS))})"
            )

    normalized_pos: str | None = None
    if pos is not None:
        normalized_pos = _clean_tsv_cell(pos) or None

    unique_lemmas: list[str] = []
    seen: set[str] = set()
    for raw_term in words:
        if not isinstance(raw_term, str):
            raise ValueError("Each word must be a string")
        if any(ch in raw_term for ch in ("\t", "\r", "\n")):
            raise ValueError(f"Invalid word {raw_term!r}: must not contain tabs or newlines")
        lemma = " ".join(raw_term.strip().lower().split())
        if not lemma:
            raise ValueError("Word cannot be empty")
        if lemma not in seen:
            seen.add(lemma)
            unique_lemmas.append(lemma)

    added: list[dict[str, Any]] = []
    skipped_existing: list[str] = []

    try:
        to_insert: list[str] = []
        for lemma in unique_lemmas:
            existing = conn.execute("SELECT id FROM words WHERE lemma = ?", (lemma,)).fetchone()
            if existing is not None:
                skipped_existing.append(lemma)
            else:
                to_insert.append(lemma)

        if to_insert:
            if batch_number is not None:
                current_batch = batch_number
                current_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM words WHERE batch_number = ?",
                        (current_batch,),
                    ).fetchone()[0]
                )
            else:
                max_batch_row = conn.execute("SELECT MAX(batch_number) AS max_batch FROM words").fetchone()
                max_batch = max_batch_row["max_batch"]
                if max_batch is None:
                    current_batch = 1
                    current_count = 0
                else:
                    max_batch_int = int(max_batch)
                    has_closed = (
                        conn.execute(
                            """
                            SELECT 1 FROM words
                            WHERE batch_number = ? AND status IN ('exported', 'mastered')
                            LIMIT 1
                            """,
                            (max_batch_int,),
                        ).fetchone()
                        is not None
                    )
                    if has_closed:
                        current_batch = max_batch_int + 1
                        current_count = 0
                    else:
                        current_count = int(
                            conn.execute(
                                "SELECT COUNT(*) FROM words WHERE batch_number = ?",
                                (max_batch_int,),
                            ).fetchone()[0]
                        )
                        if current_count >= batch_size:
                            current_batch = max_batch_int + 1
                            current_count = 0
                        else:
                            current_batch = max_batch_int

            for lemma in to_insert:
                if batch_number is None and current_count >= batch_size:
                    current_batch += 1
                    current_count = 0

                current_count += 1
                priority_score = 5_000_000.0 + current_batch * 1000.0 + current_count
                cur = conn.execute(
                    """
                    INSERT INTO words (
                        lemma, in_oxford, in_ngsl, cefr_level, pos,
                        tier, priority_score, batch_number, status
                    ) VALUES (?, 0, 0, ?, ?, 5, ?, ?, 'pending')
                    """,
                    (lemma, normalized_cefr, normalized_pos, priority_score, current_batch),
                )
                added.append(
                    {
                        "id": int(cur.lastrowid),
                        "lemma": lemma,
                        "batch_number": current_batch,
                    }
                )

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "added": added,
        "skipped_existing": skipped_existing,
        "added_count": len(added),
        "skipped_count": len(skipped_existing),
    }
