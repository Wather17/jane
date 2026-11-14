"""Unit and integration tests for Jane CLI and SQLite pipeline."""

from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jane.cli import main as cli_main

from jane.core import export_batch, get_next_batch, get_status, master_batch, save_cards
from jane.db import get_connection, init_db
from jane.seed import seed_database


class JanePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.conn = get_connection(self.db_path)
        init_db(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_seed_full_and_idempotent(self) -> None:
        first = seed_database(self.conn, batch_size=120)
        self.assertEqual(first["total"], 3705)
        self.assertEqual(first["inserted"], 3705)
        self.assertEqual(first["updated"], 0)

        second = seed_database(self.conn, batch_size=120)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["updated"], 3705)

        # Top functional words must be in batch 1
        row = self.conn.execute("SELECT batch_number, tier FROM words WHERE lemma = 'the'").fetchone()
        self.assertEqual(row["batch_number"], 1)
        self.assertEqual(row["tier"], 1)

    def test_seed_50_word_sample_and_full_flow(self) -> None:
        res = seed_database(self.conn, batch_size=50, sample_size=50, rng_seed=42)
        self.assertEqual(res["total"], 50)

        nxt = get_next_batch(self.conn, batch_number=1, limit=2)
        self.assertEqual(nxt["pending_count"], 2)
        w1, w2 = nxt["pending_words"][0]["lemma"], nxt["pending_words"][1]["lemma"]

        payload = [
            {
                "lemma": w1,
                "difficulty": "easy",
                "sentence_display": f"I see <b>{w1}</b> here.",
                "sentence_audio": f"I see {w1} here.",
                "sentence_pt": f"Eu vejo {w1} aqui.",
                "word_meaning_pt": "sentido teste 1",
                "notes": "nota 1",
            },
            {
                "lemma": w2,
                "difficulty": "medium",
                "sentence_display": f"She wants <b>{w2}</b> today.",
                "sentence_audio": f"She wants {w2} today.",
                "sentence_pt": f"Ela quer {w2} hoje.",
                "word_meaning_pt": "sentido teste 2",
            },
        ]
        saved = save_cards(self.conn, payload)
        self.assertEqual(saved["saved"], 2)

        tsv_path = Path(self.tmp.name) / "batch_01.tsv"
        exp = export_batch(self.conn, batch_number=1, out_path=tsv_path)
        self.assertEqual(exp["cards_exported"], 2)
        self.assertEqual(exp["hypertts_estimate"]["2x_openai"], exp["total_chars"] * 2)
        self.assertEqual(exp["hypertts_estimate"]["15x_elevenlabs"], exp["total_chars"] * 15)

        with tsv_path.open(encoding="utf-8") as f:
            rows = list(csv.reader(f, delimiter="\t"))
        self.assertEqual(len(rows), 3)  # header + 2 cards
        self.assertTrue(rows[1][0].startswith("jane_"))

        master_res = master_batch(self.conn, batch_number=1)
        self.assertEqual(master_res["updated"], 50)
        status = get_status(self.conn)
        self.assertEqual(status["totals"]["mastered"], 50)

    def test_save_rejects_html_in_audio_and_mismatch(self) -> None:
        seed_database(self.conn, batch_size=50, sample_size=10, rng_seed=7)
        lemma = get_next_batch(self.conn, batch_number=1, limit=1)["pending_words"][0]["lemma"]

        bad_html = [
            {
                "lemma": lemma,
                "difficulty": "easy",
                "sentence_display": f"I like <b>{lemma}</b> now.",
                "sentence_audio": f"I like <b>{lemma}</b> now.",
                "sentence_pt": "Eu gosto disso agora.",
                "word_meaning_pt": "teste",
            }
        ]
        with self.assertRaises(ValueError):
            save_cards(self.conn, bad_html)

        bad_mismatch = [
            {
                "lemma": lemma,
                "difficulty": "easy",
                "sentence_display": f"I like <b>{lemma}</b> now.",
                "sentence_audio": f"I love {lemma} now.",
                "sentence_pt": "Eu gosto disso agora.",
                "word_meaning_pt": "teste",
            }
        ]
        with self.assertRaises(ValueError):
            save_cards(self.conn, bad_mismatch)

    def test_cli_save_from_stdin(self) -> None:
        seed_database(self.conn, batch_size=50, sample_size=5, rng_seed=9)
        lemma = get_next_batch(self.conn, batch_number=1, limit=1)["pending_words"][0]["lemma"]
        payload = json.dumps(
            [
                {
                    "lemma": lemma,
                    "difficulty": "easy",
                    "sentence_display": f"We need <b>{lemma}</b> today.",
                    "sentence_audio": f"We need {lemma} today.",
                    "sentence_pt": f"Nós precisamos de {lemma} hoje.",
                    "word_meaning_pt": "teste stdin",
                }
            ]
        )
        with patch.object(sys, "stdin", io.StringIO(payload)):
            exit_code = cli_main(["--db", str(self.db_path), "save", "--file", "-"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(get_status(self.conn)["totals"]["generated"], 1)


if __name__ == "__main__":
    unittest.main()
