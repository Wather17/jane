"""Command-line interface for Jane."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jane import __version__
from jane.anki_template import generate_template_apkg
from jane.core import add_words, export_batch, export_cards, get_next_batch, get_status, master_batch, save_cards
from jane.db import get_connection, init_db
from jane.paths import (
    default_anki_dir,
    default_db_path,
    default_exports_dir,
    default_raw_dir,
    resolve_jane_home,
)
from jane.rebuild import rebuild_database
from jane.seed import seed_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jane", description="Jane — Anki English Vocabulary CLI")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--home",
        type=Path,
        default=None,
        help="Base Jane workspace directory (overrides JANE_HOME)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to SQLite database (default: <jane_home>/data/jane.db)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Populate SQLite from raw NGSL + Oxford 3000 datasets")
    p_seed.add_argument("--batch-size", type=int, default=120, help="Words per batch (default: 120)")
    p_seed.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Directory with raw datasets (default: <jane_home>/data/raw)",
    )
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

    p_export = sub.add_parser("export", help="Export cards (batch or selective subset) to UTF-8 TSV for Anki")
    export_group = p_export.add_mutually_exclusive_group(required=True)
    export_group.add_argument("--batch", type=int, default=None, help="Batch number to export")
    export_group.add_argument("--uids", type=str, default=None, help="Comma-separated Card_UIDs to export")
    export_group.add_argument("--words", type=str, default=None, help="Comma-separated lemmas to export")
    export_group.add_argument(
        "--modified",
        action="store_true",
        help="Export cards never exported or modified since last export",
    )
    export_group.add_argument(
        "--since",
        type=str,
        default=None,
        help="Export cards created/updated on or after YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS",
    )
    p_export.add_argument("--out", type=Path, default=None, help="Output TSV file path")
    p_export.add_argument("--no-header", action="store_true", help="Omit TSV header row")

    p_master = sub.add_parser("master", help="Mark all words in a batch as mastered")
    p_master.add_argument("--batch", type=int, required=True, help="Batch number")

    p_template = sub.add_parser("template", help="Generate .apkg file with the 'Jane Vocab' Anki note type")
    p_template.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output .apkg path (default: <jane_home>/anki/jane_vocab_template.apkg)",
    )

    p_rebuild = sub.add_parser("rebuild", help="Rebuild SQLite database from raw datasets and exported TSVs")
    p_rebuild.add_argument(
        "--exports-dir",
        type=Path,
        default=None,
        help="Directory containing exported batch_*.tsv files (default: <jane_home>/exports)",
    )
    p_rebuild.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Directory with raw datasets (default: <jane_home>/data/raw)",
    )
    p_rebuild.add_argument("--batch-size", type=int, default=120, help="Words per batch for seeding (default: 120)")
    p_rebuild.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip seeding from raw datasets and import cards from TSVs only",
    )

    p_add = sub.add_parser("add", help="Add custom words or expressions to the vocabulary database")
    p_add.add_argument("words", nargs="+", help="One or more custom words or expressions")
    p_add.add_argument("--batch", type=int, default=None, help="Explicit target batch number (must be > 0)")
    p_add.add_argument("--batch-size", type=int, default=120, help="Max words per batch for auto-allocation")
    p_add.add_argument("--pos", type=str, default=None, help="Part of speech (e.g. 'phrasal verb', 'noun')")
    p_add.add_argument("--cefr", type=str, default=None, help="Optional CEFR level (A1, A2, B1, B2, C1, C2)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    home = resolve_jane_home(args.home)

    if args.command == "template":
        try:
            anki_dir = default_anki_dir(home)
            out_path = args.out if args.out is not None else anki_dir / "jane_vocab_template.apkg"
            out = generate_template_apkg(out_path=out_path, anki_dir=anki_dir)
            print(json.dumps({"template_apkg": str(out)}, indent=2))
            return 0
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    db_path = args.db if args.db is not None else default_db_path(home)
    conn = get_connection(db_path)
    try:
        init_db(conn)
        if args.command == "seed":
            raw_dir = args.raw_dir if args.raw_dir is not None else default_raw_dir(home)
            res = seed_database(
                conn,
                batch_size=args.batch_size,
                raw_dir=raw_dir,
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
            if args.batch is not None:
                res = export_batch(
                    conn,
                    batch_number=args.batch,
                    out_path=args.out,
                    include_header=not args.no_header,
                    exports_dir=default_exports_dir(home),
                )
            else:
                res = export_cards(
                    conn,
                    uids=args.uids,
                    words=args.words,
                    modified=args.modified,
                    since=args.since,
                    out_path=args.out,
                    include_header=not args.no_header,
                    exports_dir=default_exports_dir(home),
                )
            print(json.dumps(res, indent=2))
        elif args.command == "master":
            res = master_batch(conn, batch_number=args.batch)
            print(json.dumps(res, indent=2))
        elif args.command == "rebuild":
            exports_dir = args.exports_dir if args.exports_dir is not None else default_exports_dir(home)
            raw_dir = args.raw_dir if args.raw_dir is not None else default_raw_dir(home)
            res = rebuild_database(
                conn,
                exports_dir=exports_dir,
                raw_dir=raw_dir,
                batch_size=args.batch_size,
                skip_seed=args.skip_seed,
            )
            print(json.dumps(res, indent=2))
        elif args.command == "add":
            res = add_words(
                conn,
                words=args.words,
                batch_number=args.batch,
                batch_size=args.batch_size,
                pos=args.pos,
                cefr_level=args.cefr,
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    return 0
