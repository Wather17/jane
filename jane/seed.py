"""Seed the SQLite database from raw NGSL and Oxford 3000 datasets."""

from __future__ import annotations

import csv
import json
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path

RAW_DIR = Path("data/raw")
CEFR_WEIGHT = {"A1": 1, "A2": 2, "B1": 3, "B2": 4}


@dataclass
class WordRecord:
    lemma: str
    in_oxford: int
    in_ngsl: int
    cefr_level: str | None
    pos: str | None
    ngsl_rank: int | None
    ngsl_freq: float | None
    tier: int
    priority_score: float


def _load_ngsl(path: Path) -> dict[str, tuple[int, float]]:
    data: dict[str, tuple[int, float]] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lemma = row["Lemma"].strip().lower()
            if not lemma:
                continue
            rank = int(row["SFI Rank"])
            freq = float(row["Adjusted Frequency per Million (U)"])
            data[lemma] = (rank, freq)
    return data


def _load_oxford_flat(path: Path) -> set[str]:
    with path.open(encoding="utf-8") as f:
        return {w.strip().lower() for w in json.load(f) if isinstance(w, str) and w.strip()}


def _load_oxford_cefr(path: Path) -> dict[str, tuple[str, str]]:
    """Return {lemma: (lowest_cefr_level, combined_pos)} for A1-B2 entries."""
    grouped: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8") as f:
        entries = json.load(f)

    for item in entries:
        word = (item.get("word") or "").strip().lower()
        level = item.get("level")
        pos = (item.get("type") or "").strip().lower()
        if not word or level not in CEFR_WEIGHT:
            continue

        existing = grouped.get(word)
        if existing is None:
            grouped[word] = {"level": level, "pos": [pos] if pos else []}
        else:
            if CEFR_WEIGHT[level] < CEFR_WEIGHT[existing["level"]]:  # type: ignore[index]
                existing["level"] = level
            pos_list: list[str] = existing["pos"]  # type: ignore[assignment]
            if pos and pos not in pos_list:
                pos_list.append(pos)

    return {
        word: (str(meta["level"]), ", ".join(meta["pos"]) if meta["pos"] else "")  # type: ignore[arg-type]
        for word, meta in grouped.items()
    }


def _compute_tier_and_score(
    lemma: str,
    in_oxford: int,
    in_ngsl: int,
    cefr_level: str | None,
    ngsl_rank: int | None,
) -> tuple[int, float]:
    if in_oxford and in_ngsl:
        tier = 1
    elif in_ngsl:
        tier = 2
    elif cefr_level is not None:
        tier = 3
    else:
        tier = 4

    # Ultra-basic functional words (top 150 NGSL) stay at the very front of Tier 1
    if tier == 1 and ngsl_rank is not None and ngsl_rank <= 150:
        score = float(ngsl_rank)
        return tier, score

    cefr_w = CEFR_WEIGHT.get(cefr_level or "", 5)
    rank_w = ngsl_rank if ngsl_rank is not None else 9999
    # Keep alphabetical tie-breaker deterministic via small fractional offset
    alpha_tie = sum((ord(c) - 96) / (100 ** (i + 1)) for i, c in enumerate(lemma[:4]) if c.isalpha())
    score = tier * 1_000_000 + cefr_w * 10_000 + rank_w + alpha_tie
    return tier, score


def build_word_records(raw_dir: Path = RAW_DIR) -> list[WordRecord]:
    """Load, merge, and sort all words from NGSL and Oxford 3000."""
    ngsl = _load_ngsl(raw_dir / "ngsl_12_stats.csv")
    ox_flat = _load_oxford_flat(raw_dir / "oxford_3000.json")
    ox_cefr = _load_oxford_cefr(raw_dir / "oxford_cefr.json")

    union_lemmas = sorted(set(ngsl.keys()) | ox_flat)
    records: list[WordRecord] = []

    for lemma in union_lemmas:
        in_oxford = 1 if lemma in ox_flat else 0
        in_ngsl = 1 if lemma in ngsl else 0
        ngsl_rank, ngsl_freq = ngsl.get(lemma, (None, None))
        cefr_level, pos = ox_cefr.get(lemma, (None, None))
        if pos == "":
            pos = None

        tier, score = _compute_tier_and_score(lemma, in_oxford, in_ngsl, cefr_level, ngsl_rank)
        records.append(
            WordRecord(
                lemma=lemma,
                in_oxford=in_oxford,
                in_ngsl=in_ngsl,
                cefr_level=cefr_level,
                pos=pos,
                ngsl_rank=ngsl_rank,
                ngsl_freq=ngsl_freq,
                tier=tier,
                priority_score=score,
            )
        )

    records.sort(key=lambda r: (r.priority_score, r.lemma))
    return records


def seed_database(
    conn: sqlite3.Connection,
    batch_size: int = 120,
    raw_dir: Path = RAW_DIR,
    sample_size: int | None = None,
    rng_seed: int = 42,
) -> dict[str, int]:
    """Populate words table idempotently; optionally sample N random words for testing."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    records = build_word_records(raw_dir=raw_dir)
    if sample_size is not None:
        if sample_size <= 0 or sample_size > len(records):
            raise ValueError(f"sample_size must be between 1 and {len(records)}")
        rng = random.Random(rng_seed)
        records = rng.sample(records, sample_size)
        records.sort(key=lambda r: (r.priority_score, r.lemma))

    inserted = 0
    updated = 0

    for idx, rec in enumerate(records):
        batch_number = (idx // batch_size) + 1
        existing = conn.execute("SELECT id FROM words WHERE lemma = ?", (rec.lemma,)).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO words (
                    lemma, in_oxford, in_ngsl, cefr_level, pos,
                    ngsl_rank, ngsl_freq, tier, priority_score, batch_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.lemma,
                    rec.in_oxford,
                    rec.in_ngsl,
                    rec.cefr_level,
                    rec.pos,
                    rec.ngsl_rank,
                    rec.ngsl_freq,
                    rec.tier,
                    rec.priority_score,
                    batch_number,
                ),
            )
            inserted += 1
        else:
            conn.execute(
                """
                UPDATE words SET
                    in_oxford = ?, in_ngsl = ?, cefr_level = ?, pos = ?,
                    ngsl_rank = ?, ngsl_freq = ?, tier = ?, priority_score = ?,
                    batch_number = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    rec.in_oxford,
                    rec.in_ngsl,
                    rec.cefr_level,
                    rec.pos,
                    rec.ngsl_rank,
                    rec.ngsl_freq,
                    rec.tier,
                    rec.priority_score,
                    batch_number,
                    existing["id"],
                ),
            )
            updated += 1

    conn.commit()
    return {"total": len(records), "inserted": inserted, "updated": updated}
