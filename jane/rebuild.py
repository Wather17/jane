"""Rebuild the SQLite database deterministically from raw datasets and exported TSVs."""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from jane.core import VALID_DIFFICULTIES
from jane.seed import RAW_DIR, seed_database

DEFAULT_EXPORTS_DIR = Path("exports")
BATCH_RE = re.compile(r"^(?:batch_)?(\d+)$", re.IGNORECASE)
SENSE_RE = re.compile(r"_(\d+)$")


@dataclass(frozen=True)
class ParsedTsvCard:
    source_path: Path
    line_no: int
    row_idx: int
    card_uid: str
    lemma: str
    sense_index: int
    sentence_display: str
    sentence_audio: str
    sentence_pt: str
    word_meaning_pt: str
    difficulty: str
    batch_number: int
    notes: str
    char_count: int


def _discover_batch_tsvs(exports_dir: Path) -> list[Path]:
    """Return batch_*.tsv files ordered with imported/ first, then exports_dir root."""
    files: list[Path] = []
    imported_dir = exports_dir / "imported"
    if imported_dir.is_dir():
        files.extend(sorted(p for p in imported_dir.glob("batch_*.tsv") if p.is_file()))
    if exports_dir.is_dir():
        files.extend(sorted(p for p in exports_dir.glob("batch_*.tsv") if p.is_file()))
    return files


def _parse_tsv_file(tsv_path: Path) -> list[ParsedTsvCard]:
    """Parse and validate all card rows from a single exported TSV file."""
    parsed: list[ParsedTsvCard] = []
    row_idx = 0

    with tsv_path.open("r", encoding="utf-8", newline="") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\r\n")
            if not line.strip() or line.startswith("#"):
                continue

            row = next(csv.reader([line], delimiter="\t"))
            if len(row) >= 2 and row[0].strip() == "Card_UID" and row[1].strip() == "Word":
                continue

            if len(row) < 8 or len(row) > 9:
                raise ValueError(
                    f"{tsv_path}:{line_no}: expected 8 or 9 tab-separated columns, got {len(row)}"
                )

            card_uid = row[0].strip()
            lemma = " ".join(row[1].strip().lower().split())
            sentence_display = row[2].strip()
            sentence_audio = row[3].strip()
            sentence_pt = row[4].strip()
            word_meaning_pt = row[5].strip()
            difficulty = row[6].strip().lower()
            batch_raw = row[7].strip()
            notes = row[8].strip() if len(row) == 9 else ""

            required_checks = [
                ("Card_UID", card_uid),
                ("Word", lemma),
                ("Sentence_Display", sentence_display),
                ("Sentence_Audio", sentence_audio),
                ("Sentence_PT", sentence_pt),
                ("Word_Meaning_PT", word_meaning_pt),
            ]
            for col_name, value in required_checks:
                if not value:
                    raise ValueError(f"{tsv_path}:{line_no}: missing required column '{col_name}'")

            if difficulty not in VALID_DIFFICULTIES:
                raise ValueError(
                    f"{tsv_path}:{line_no}: invalid Difficulty '{row[6].strip()}' (expected easy|medium|hard)"
                )

            batch_match = BATCH_RE.fullmatch(batch_raw)
            if batch_match is None:
                raise ValueError(f"{tsv_path}:{line_no}: invalid Batch '{batch_raw}'")
            batch_number = int(batch_match.group(1))
            if batch_number <= 0:
                raise ValueError(f"{tsv_path}:{line_no}: invalid Batch '{batch_raw}' (must be >= 1)")

            sense_match = SENSE_RE.search(card_uid)
            sense_index = int(sense_match.group(1)) if sense_match else 1
            if sense_index <= 0:
                raise ValueError(
                    f"{tsv_path}:{line_no}: invalid sense index in Card_UID '{card_uid}' (must be >= 1)"
                )

            row_idx += 1
            parsed.append(
                ParsedTsvCard(
                    source_path=tsv_path,
                    line_no=line_no,
                    row_idx=row_idx,
                    card_uid=card_uid,
                    lemma=lemma,
                    sense_index=sense_index,
                    sentence_display=sentence_display,
                    sentence_audio=sentence_audio,
                    sentence_pt=sentence_pt,
                    word_meaning_pt=word_meaning_pt,
                    difficulty=difficulty,
                    batch_number=batch_number,
                    notes=notes,
                    char_count=len(sentence_audio),
                )
            )

    return parsed


def rebuild_database(
    conn: sqlite3.Connection,
    exports_dir: Path = DEFAULT_EXPORTS_DIR,
    raw_dir: Path = RAW_DIR,
    batch_size: int = 120,
    skip_seed: bool = False,
) -> dict[str, int]:
    """Rebuild SQLite state from raw datasets (optional) and exported batch_*.tsv files."""
    if not skip_seed and batch_size <= 0:
        raise ValueError("batch_size must be positive")

    tsv_files = _discover_batch_tsvs(Path(exports_dir))
    all_cards: list[ParsedTsvCard] = []
    for tsv_path in tsv_files:
        all_cards.extend(_parse_tsv_file(tsv_path))

    if not skip_seed:
        seed_database(conn, batch_size=batch_size, raw_dir=raw_dir)

    cards_imported = 0
    cards_updated = 0
    custom_words_created = 0
    processed_chars: dict[str, int] = {}

    try:
        for card in all_cards:
            word_row = conn.execute(
                "SELECT id, pos, status FROM words WHERE lemma = ?",
                (card.lemma,),
            ).fetchone()

            if word_row is None:
                priority_score = float(5_000_000 + card.batch_number * 1000 + card.row_idx)
                cur = conn.execute(
                    """
                    INSERT INTO words (
                        lemma, in_oxford, in_ngsl, tier, priority_score, batch_number, status
                    ) VALUES (?, 0, 0, 5, ?, ?, 'exported')
                    """,
                    (card.lemma, priority_score, card.batch_number),
                )
                word_id = int(cur.lastrowid)
                word_pos = None
                custom_words_created += 1
            else:
                word_id = int(word_row["id"])
                word_pos = word_row["pos"]
                if word_row["status"] in ("pending", "generated"):
                    conn.execute(
                        "UPDATE words SET status = 'exported', updated_at = datetime('now') WHERE id = ?",
                        (word_id,),
                    )

            by_uid = conn.execute(
                "SELECT id, word_id, sense_index FROM cards WHERE card_uid = ?",
                (card.card_uid,),
            ).fetchone()
            by_word_sense = conn.execute(
                "SELECT id, card_uid FROM cards WHERE word_id = ? AND sense_index = ?",
                (word_id, card.sense_index),
            ).fetchone()

            if by_uid is not None and (by_word_sense is None or by_word_sense["id"] == by_uid["id"]):
                conn.execute(
                    """
                    UPDATE cards SET
                        word_id = ?, sense_index = ?, pos = COALESCE(pos, ?), difficulty = ?,
                        sentence_display = ?, sentence_audio = ?, sentence_pt = ?,
                        word_meaning_pt = ?, notes = ?, char_count = ?,
                        updated_at = datetime('now'), exported_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        word_id,
                        card.sense_index,
                        word_pos,
                        card.difficulty,
                        card.sentence_display,
                        card.sentence_audio,
                        card.sentence_pt,
                        card.word_meaning_pt,
                        card.notes,
                        card.char_count,
                        by_uid["id"],
                    ),
                )
                cards_updated += 1
            elif by_uid is None and by_word_sense is None:
                conn.execute(
                    """
                    INSERT INTO cards (
                        card_uid, word_id, sense_index, pos, difficulty,
                        sentence_display, sentence_audio, sentence_pt,
                        word_meaning_pt, notes, char_count, updated_at, exported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    (
                        card.card_uid,
                        word_id,
                        card.sense_index,
                        word_pos,
                        card.difficulty,
                        card.sentence_display,
                        card.sentence_audio,
                        card.sentence_pt,
                        card.word_meaning_pt,
                        card.notes,
                        card.char_count,
                    ),
                )
                cards_imported += 1
            else:
                existing_uid = by_word_sense["card_uid"] if by_word_sense is not None else card.card_uid
                raise ValueError(
                    f"{card.source_path}:{card.line_no}: card conflict for lemma '{card.lemma}' "
                    f"(sense {card.sense_index}): TSV Card_UID '{card.card_uid}' conflicts with "
                    f"existing Card_UID '{existing_uid}'"
                )

            processed_chars[card.card_uid] = card.char_count

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "files_processed": len(tsv_files),
        "cards_imported": cards_imported,
        "cards_updated": cards_updated,
        "custom_words_created": custom_words_created,
        "total_chars": sum(processed_chars.values()),
    }
