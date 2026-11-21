"""Unit and integration tests for Jane CLI and SQLite pipeline."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from jane.anki_template import NOTE_FIELDS, NOTETYPE_NAME, generate_template_apkg
from jane.cli import main as cli_main

from jane.core import export_batch, get_next_batch, get_status, master_batch, save_cards
from jane.db import get_connection, init_db
from jane.rebuild import rebuild_database
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

        lines = tsv_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "#separator:tab")
        self.assertEqual(lines[1], "#html:true")
        self.assertEqual(lines[2], "#notetype:Jane Vocab")
        self.assertTrue(lines[3].startswith("#columns:Card_UID\t"))
        self.assertEqual(len(lines), 6)  # 4 Anki directive lines + 2 cards
        self.assertTrue(lines[4].startswith("jane_"))

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

    def test_generate_template_apkg(self) -> None:
        apkg_path = Path(self.tmp.name) / "jane_template.apkg"
        out = generate_template_apkg(out_path=apkg_path)
        self.assertTrue(out.exists())

        with zipfile.ZipFile(out, "r") as zf:
            self.assertIn("collection.anki2", zf.namelist())
            self.assertIn("media", zf.namelist())
            zf.extract("collection.anki2", path=self.tmp.name)

        anki_conn = sqlite3.connect(Path(self.tmp.name) / "collection.anki2")
        models = json.loads(anki_conn.execute("SELECT models FROM col").fetchone()[0])
        anki_conn.close()

        model = next(iter(models.values()))
        self.assertEqual(model["name"], NOTETYPE_NAME)
        self.assertEqual([f["name"] for f in model["flds"]], NOTE_FIELDS)

    def test_next_no_known_omits_known_words(self) -> None:
        seed_database(self.conn, batch_size=2, sample_size=4, rng_seed=11)
        first = get_next_batch(self.conn, batch_number=1, limit=1)["pending_words"][0]["lemma"]
        save_cards(
            self.conn,
            [
                {
                    "lemma": first,
                    "difficulty": "easy",
                    "sentence_display": f"We saw <b>{first}</b> there.",
                    "sentence_audio": f"We saw {first} there.",
                    "sentence_pt": f"Nós vimos {first} lá.",
                    "word_meaning_pt": "teste",
                }
            ],
        )
        with_known = get_next_batch(self.conn, batch_number=2, limit=2, include_known=True)
        self.assertGreaterEqual(len(with_known["known_words"]), 2)

        without_known = get_next_batch(self.conn, batch_number=2, limit=2, include_known=False)
        self.assertEqual(without_known["known_words"], [])
        self.assertEqual(without_known["pending_count"], 2)

    def test_rebuild_from_repo_tsvs_and_idempotency(self) -> None:
        first = rebuild_database(self.conn)
        self.assertEqual(first["files_processed"], 31)
        self.assertEqual(first["cards_imported"], 3705)
        self.assertEqual(first["cards_updated"], 0)
        self.assertEqual(first["custom_words_created"], 0)
        self.assertEqual(first["total_chars"], 146682)

        status = get_status(self.conn)
        self.assertEqual(status["totals"]["words_total"], 3705)
        self.assertEqual(status["totals"]["exported"], 3705)
        self.assertEqual(status["totals"]["pending"], 0)
        self.assertEqual(status["cards"]["cards_total"], 3705)
        self.assertEqual(status["cards"]["total_chars"], 146682)

        # Verify every Card_UID matches the TSVs verbatim
        expected_uids: set[str] = set()
        for tsv_path in sorted((Path("exports") / "imported").glob("batch_*.tsv")):
            with tsv_path.open("r", encoding="utf-8", newline="") as f:
                for raw in f:
                    if not raw.strip() or raw.startswith("#"):
                        continue
                    row = next(csv.reader([raw.rstrip("\r\n")], delimiter="\t"))
                    expected_uids.add(row[0])
        actual_uids = {
            r["card_uid"] for r in self.conn.execute("SELECT card_uid FROM cards").fetchall()
        }
        self.assertEqual(actual_uids, expected_uids)

        # Second rebuild must be fully idempotent
        second = rebuild_database(self.conn)
        self.assertEqual(second["files_processed"], 31)
        self.assertEqual(second["cards_imported"], 0)
        self.assertEqual(second["cards_updated"], 3705)
        self.assertEqual(second["custom_words_created"], 0)
        self.assertEqual(second["total_chars"], 146682)
        self.assertEqual(get_status(self.conn)["cards"]["cards_total"], 3705)

    def test_rebuild_round_trip_custom_words_precedence_skip_seed_and_mastered(self) -> None:
        # Round-trip: seed -> save -> export -> rebuild into fresh DB
        seed_database(self.conn, batch_size=50, sample_size=10, rng_seed=42)
        nxt = get_next_batch(self.conn, batch_number=1, limit=2)
        w1, w2 = nxt["pending_words"][0]["lemma"], nxt["pending_words"][1]["lemma"]
        save_cards(
            self.conn,
            [
                {
                    "lemma": w1,
                    "difficulty": "easy",
                    "sentence_display": f"I use <b>{w1}</b> daily.",
                    "sentence_audio": f"I use {w1} daily.",
                    "sentence_pt": f"Eu uso {w1} diariamente.",
                    "word_meaning_pt": "sentido 1",
                },
                {
                    "lemma": w2,
                    "difficulty": "medium",
                    "sentence_display": f"They need <b>{w2}</b> soon.",
                    "sentence_audio": f"They need {w2} soon.",
                    "sentence_pt": f"Eles precisam de {w2} logo.",
                    "word_meaning_pt": "sentido 2",
                },
            ],
        )

        exports_dir = Path(self.tmp.name) / "exports"
        imported_dir = exports_dir / "imported"
        imported_dir.mkdir(parents=True)
        export_batch(self.conn, batch_number=1, out_path=imported_dir / "batch_01.tsv")

        # Put a test_*.tsv file that must be ignored
        (exports_dir / "test_50.tsv").write_text("bad\trow\n", encoding="utf-8")

        # Put an updated version of w1's card in exports/batch_01.tsv + a custom word in batch_32
        w1_uid = self.conn.execute(
            "SELECT c.card_uid FROM cards c JOIN words w ON w.id = c.word_id WHERE w.lemma = ?",
            (w1,),
        ).fetchone()["card_uid"]
        (exports_dir / "batch_01.tsv").write_text(
            "#separator:tab\n#html:true\n#notetype:Jane Vocab\n"
            f"{w1_uid}\t{w1}\tI really use <b>{w1}</b> daily.\tI really use {w1} daily.\t"
            f"Eu realmente uso {w1} diariamente.\tsentido atualizado\thard\tbatch_01\tnota nova\n",
            encoding="utf-8",
        )
        (exports_dir / "batch_32.tsv").write_text(
            "jane_9999_01\tburn out\tDo not <b>burn out</b> at work.\tDo not burn out at work.\t"
            "Não se esgote no trabalho.\tesgotar-se\tmedium\t32\tphrasal verb\n",
            encoding="utf-8",
        )

        # Fresh DB with --skip-seed (no raw_dir required)
        rebuilt_db = Path(self.tmp.name) / "rebuilt.db"
        conn2 = get_connection(rebuilt_db)
        try:
            init_db(conn2)
            res = rebuild_database(
                conn2,
                exports_dir=exports_dir,
                raw_dir=Path(self.tmp.name) / "missing_raw",
                skip_seed=True,
            )
            self.assertEqual(res["files_processed"], 3)
            self.assertEqual(res["cards_imported"], 3)
            self.assertEqual(res["cards_updated"], 1)  # exports/batch_01.tsv overrode imported/batch_01.tsv
            self.assertEqual(res["custom_words_created"], 3)

            # Precedence: exports/batch_01.tsv won over exports/imported/batch_01.tsv
            updated_card = conn2.execute(
                "SELECT sentence_audio, difficulty, notes FROM cards WHERE card_uid = ?",
                (w1_uid,),
            ).fetchone()
            self.assertEqual(updated_card["sentence_audio"], f"I really use {w1} daily.")
            self.assertEqual(updated_card["difficulty"], "hard")
            self.assertEqual(updated_card["notes"], "nota nova")

            # Custom word metadata and exact Card_UID preserved
            custom_word = conn2.execute(
                "SELECT tier, batch_number, status, in_oxford, in_ngsl FROM words WHERE lemma = 'burn out'"
            ).fetchone()
            self.assertEqual(custom_word["tier"], 5)
            self.assertEqual(custom_word["batch_number"], 32)
            self.assertEqual(custom_word["status"], "exported")
            self.assertEqual(custom_word["in_oxford"], 0)
            self.assertEqual(custom_word["in_ngsl"], 0)
            custom_card = conn2.execute(
                "SELECT card_uid FROM cards WHERE card_uid = 'jane_9999_01'"
            ).fetchone()
            self.assertIsNotNone(custom_card)

            # Preserve 'mastered' status across subsequent rebuilds
            master_batch(conn2, batch_number=32)
            rebuild_database(conn2, exports_dir=exports_dir, skip_seed=True)
            still_mastered = conn2.execute(
                "SELECT status FROM words WHERE lemma = 'burn out'"
            ).fetchone()["status"]
            self.assertEqual(still_mastered, "mastered")
        finally:
            conn2.close()

    def test_rebuild_empty_dir_and_malformed_tsv_rollback(self) -> None:
        empty_dir = Path(self.tmp.name) / "empty_exports"
        empty_dir.mkdir()
        empty_res = rebuild_database(self.conn, exports_dir=empty_dir, skip_seed=True)
        self.assertEqual(empty_res["files_processed"], 0)
        self.assertEqual(empty_res["cards_imported"], 0)
        self.assertEqual(empty_res["total_chars"], 0)

        # Malformed TSV must rollback completely and return CLI exit code 1 with file and line info
        bad_dir = Path(self.tmp.name) / "bad_exports"
        bad_dir.mkdir()
        bad_tsv = bad_dir / "batch_01.tsv"
        bad_tsv.write_text(
            "#separator:tab\n"
            "jane_0001_01\talpha\tI see <b>alpha</b> now.\tI see alpha now.\tEu vejo alpha.\talfa\teasy\tbatch_01\t\n"
            "jane_0002_01\tbeta\tI see <b>beta</b> now.\tI see beta now.\tEu vejo beta.\tbeta\tinvalid_diff\tbatch_01\t\n",
            encoding="utf-8",
        )
        stderr_buf = io.StringIO()
        with patch.object(sys, "stderr", stderr_buf):
            code = cli_main(
                ["--db", str(self.db_path), "rebuild", "--exports-dir", str(bad_dir), "--skip-seed"]
            )
        self.assertEqual(code, 1)
        err_text = stderr_buf.getvalue()
        self.assertIn("batch_01.tsv:3", err_text)
        # Ensure rollback left DB clean
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM words").fetchone()[0], 0)

        # Conflicting Card_UID for existing (word_id, sense_index) must fail and rollback
        good_dir = Path(self.tmp.name) / "good_exports"
        good_dir.mkdir()
        (good_dir / "batch_01.tsv").write_text(
            "jane_0001_01\talpha\tI see <b>alpha</b> now.\tI see alpha now.\tEu vejo alpha.\talfa\teasy\tbatch_01\t\n",
            encoding="utf-8",
        )
        rebuild_database(self.conn, exports_dir=good_dir, skip_seed=True)

        conflict_dir = Path(self.tmp.name) / "conflict_exports"
        conflict_dir.mkdir()
        (conflict_dir / "batch_01.tsv").write_text(
            "jane_0002_01\tgamma\tI see <b>gamma</b> now.\tI see gamma now.\tEu vejo gamma.\tgama\teasy\tbatch_01\t\n"
            "jane_9999_01\talpha\tI see <b>alpha</b> again.\tI see alpha again.\tEu vejo alpha.\talfa\teasy\tbatch_01\t\n",
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            rebuild_database(self.conn, exports_dir=conflict_dir, skip_seed=True)
        # Ensure gamma from line 1 was rolled back too
        self.assertIsNone(
            self.conn.execute("SELECT id FROM words WHERE lemma = 'gamma'").fetchone()
        )


if __name__ == "__main__":
    unittest.main()
