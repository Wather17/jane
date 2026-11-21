"""Command-line interface for Jane."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jane.anki_template import ANKI_DIR, generate_template_apkg
from jane.core import export_batch, get_next_batch, get_status, master_batch, save_cards
from jane.db import DEFAULT_DB_PATH, get_connection, init_db
from jane.rebuild import DEFAULT_EXPORTS_DIR, rebuild_database
from jane.seed import RAW_DIR, seed_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jane", description="Jane — Anki English Vocabulary CLI")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")

    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Populate SQLite from raw NGSL + Oxford 3000 datasets")
    p_seed.add_argument("--batch-size", type=int, default=120, help="Words per batch (default: 120)")
    p_seed.add_argument("--raw-dir", type=Path, default=RAW_DIR, help="Directory with raw datasets")
    p_seed.add_argument("--sample", type=int, default=None, help="Sample N random words (for sandbox testing)")
    p_seed.add_argument("--rng-seed", type=int, default=42, help="Random seed for --sample")

    sub.add_parser("status", help="Show database and batch progress")

    p_next = sub.add_parser("next", help="Get next pending words for a batch as JSON")
    p_next.add_argument("--batch", type=int, default=1, help="Batch number (default: 1)")
    p_next.add_argument("--limit", type=int, default=20, help="Max pending words to return")
    p_next.add_argument("--no-known", action="store_true", help="Omit known_words list from output")

    p_save = sub.add_parser("save", help="Validate and save generated cards from a JSON file (or '-' for stdin)")
    p_save.add_argument("--file", type=str, required=True, help="Path to JSON array of cards, or '-' for stdin")
    p_save.add_argument("--force", action="store_true", help="Overwrite existing cards")

    p_export = sub.add_parser("export", help="Export a batch to UTF-8 TSV for Anki")
    p_export.add_argument("--batch", type=int, required=True, help="Batch number to export")
    p_export.add_argument("--out", type=Path, default=None, help="Output TSV file path")
    p_export.add_argument("--no-header", action="store_true", help="Omit TSV header row")

    p_master = sub.add_parser("master", help="Mark all words in a batch as mastered")
    p_master.add_argument("--batch", type=int, required=True, help="Batch number")

    p_template = sub.add_parser("template", help="Generate .apkg file with the 'Jane Vocab' Anki note type")
    p_template.add_argument(
        "--out",
        type=Path,
        default=ANKI_DIR / "jane_vocab_template.apkg",
        help="Output .apkg path (default: anki/jane_vocab_template.apkg)",
    )

    p_rebuild = sub.add_parser("rebuild", help="Rebuild SQLite database from raw datasets and exported TSVs")
    p_rebuild.add_argument(
        "--exports-dir",
        type=Path,
        default=DEFAULT_EXPORTS_DIR,
        help="Directory containing exported batch_*.tsv files (default: exports)",
    )
    p_rebuild.add_argument("--raw-dir", type=Path, default=RAW_DIR, help="Directory with raw datasets")
    p_rebuild.add_argument("--batch-size", type=int, default=120, help="Words per batch for seeding (default: 120)")
    p_rebuild.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip seeding from raw datasets and import cards from TSVs only",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    conn = get_connection(args.db)
    try:
        init_db(conn)
        if args.command == "seed":
            res = seed_database(
                conn,
                batch_size=args.batch_size,
                raw_dir=args.raw_dir,
                sample_size=args.sample,
                rng_seed=args.rng_seed,
            )
            print(json.dumps(res, indent=2))
        elif args.command == "status":
            res = get_status(conn)
            print(json.dumps(res, indent=2))
        elif args.command == "next":
            res = get_next_batch(
                conn,
                batch_number=args.batch,
                limit=args.limit,
                include_known=not args.no_known,
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
        elif args.command == "save":
            raw_json = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
            items = json.loads(raw_json)
            res = save_cards(conn, items, force=args.force)
            print(json.dumps(res, indent=2))
        elif args.command == "export":
            res = export_batch(
                conn,
                batch_number=args.batch,
                out_path=args.out,
                include_header=not args.no_header,
            )
            print(json.dumps(res, indent=2))
        elif args.command == "master":
            res = master_batch(conn, batch_number=args.batch)
            print(json.dumps(res, indent=2))
        elif args.command == "template":
            out = generate_template_apkg(out_path=args.out)
            print(json.dumps({"template_apkg": str(out)}, indent=2))
        elif args.command == "rebuild":
            res = rebuild_database(
                conn,
                exports_dir=args.exports_dir,
                raw_dir=args.raw_dir,
                batch_size=args.batch_size,
                skip_seed=args.skip_seed,
            )
            print(json.dumps(res, indent=2))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    return 0
