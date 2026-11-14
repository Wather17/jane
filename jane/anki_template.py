"""Generate a standalone .apkg containing the 'Jane Vocab' Anki Note Type."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path

ANKI_DIR = Path("anki")
NOTETYPE_NAME = "Jane Vocab"
NOTE_FIELDS = [
    "Card_UID",
    "Word",
    "Sentence_Display",
    "Sentence_Audio",
    "Sentence_PT",
    "Word_Meaning_PT",
    "Difficulty",
    "Batch",
    "Notes",
    "Audio_Sentence",
]

# Fixed IDs ensure re-importing updates the same Note Type cleanly
MODEL_ID = 1731600001001
DECK_ID = 1731600002001

ANKI_COLLECTION_SCHEMA = """
CREATE TABLE col (
    id integer primary key,
    crt integer not null,
    mod integer not null,
    scm integer not null,
    ver integer not null,
    dty integer not null,
    usn integer not null,
    ls integer not null,
    conf text not null,
    models text not null,
    decks text not null,
    dconf text not null,
    tags text not null
);
CREATE TABLE notes (
    id integer primary key,
    guid text not null,
    mid integer not null,
    mod integer not null,
    usn integer not null,
    tags text not null,
    flds text not null,
    sfld integer not null,
    csum integer not null,
    flags integer not null,
    data text not null
);
CREATE TABLE cards (
    id integer primary key,
    nid integer not null,
    did integer not null,
    ord integer not null,
    mod integer not null,
    usn integer not null,
    type integer not null,
    queue integer not null,
    due integer not null,
    ivl integer not null,
    factor integer not null,
    reps integer not null,
    lapses integer not null,
    left integer not null,
    odue integer not null,
    odid integer not null,
    flags integer not null,
    data text not null
);
CREATE TABLE revlog (
    id integer primary key,
    cid integer not null,
    usn integer not null,
    ease integer not null,
    ivl integer not null,
    lastIvl integer not null,
    factor integer not null,
    time integer not null,
    type integer not null
);
CREATE TABLE graves (
    usn integer not null,
    oid integer not null,
    type integer not null
);
"""


def _field_checksum(text: str) -> int:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def generate_template_apkg(
    out_path: Path = ANKI_DIR / "jane_vocab_template.apkg",
    anki_dir: Path = ANKI_DIR,
) -> Path:
    """Build a minimal .apkg file with the 'Jane Vocab' note type and 1 sample card."""
    front_html = (anki_dir / "front.html").read_text(encoding="utf-8")
    back_html = (anki_dir / "back.html").read_text(encoding="utf-8")
    style_css = (anki_dir / "style.css").read_text(encoding="utf-8")

    now_s = int(time.time())
    now_ms = now_s * 1000

    fields_meta = [
        {
            "name": name,
            "ord": idx,
            "sticky": False,
            "rtl": False,
            "font": "Arial",
            "size": 20,
            "media": [],
        }
        for idx, name in enumerate(NOTE_FIELDS)
    ]

    models = {
        str(MODEL_ID): {
            "id": MODEL_ID,
            "name": NOTETYPE_NAME,
            "type": 0,
            "mod": now_s,
            "usn": -1,
            "sortf": 0,
            "did": DECK_ID,
            "tmpls": [
                {
                    "name": "Recognition",
                    "ord": 0,
                    "qfmt": front_html,
                    "afmt": back_html,
                    "bqfmt": "",
                    "bafmt": "",
                    "did": None,
                }
            ],
            "flds": fields_meta,
            "css": style_css,
            "latexPre": "",
            "latexPost": "",
            "req": [[0, "any", [2]]],
            "tags": [],
            "vers": [],
        }
    }

    decks = {
        "1": {
            "id": 1,
            "name": "Default",
            "mod": now_s,
            "usn": -1,
            "lrnToday": [0, 0],
            "revToday": [0, 0],
            "newToday": [0, 0],
            "timeToday": [0, 0],
            "collapsed": False,
            "desc": "",
            "dyn": 0,
            "conf": 1,
            "extendNew": 10,
            "extendRev": 50,
        },
        str(DECK_ID): {
            "id": DECK_ID,
            "name": "Jane Template (apague este card após importar)",
            "mod": now_s,
            "usn": -1,
            "lrnToday": [0, 0],
            "revToday": [0, 0],
            "newToday": [0, 0],
            "timeToday": [0, 0],
            "collapsed": False,
            "desc": "Instala o Tipo de Nota 'Jane Vocab' no Anki.",
            "dyn": 0,
            "conf": 1,
            "extendNew": 10,
            "extendRev": 50,
        },
    }

    dconf = {
        "1": {
            "id": 1,
            "name": "Default",
            "replayq": True,
            "lapse": {"leechFails": 8, "minInt": 1, "delays": [10], "leechAction": 0, "mult": 0},
            "rev": {"perDay": 200, "fuzz": 0.05, "ivlFct": 1, "maxIvl": 36500, "ease4": 1.3, "bury": True, "minSpace": 1},
            "timer": 0,
            "maxTaken": 60,
            "usn": 0,
            "new": {"perDay": 20, "delays": [1, 10], "separate": True, "ints": [1, 4, 7], "initialFactor": 2500, "bury": True, "order": 1},
            "mod": 0,
            "autoplay": True,
        }
    }

    conf = {
        "nextPos": 1,
        "estTimes": True,
        "activeDecks": [1],
        "sortType": "noteFld",
        "timeLim": 0,
        "sortBackwards": False,
        "addToCur": True,
        "curDeck": 1,
        "newBury": True,
        "newSpread": 0,
        "dueCounts": True,
        "curModel": str(MODEL_ID),
        "collapseTime": 1200,
    }

    sample_fields = [
        "jane_template_0001",
        "water",
        "I drink <b>water</b> every morning.",
        "I drink water every morning.",
        "Eu bebo água toda manhã.",
        "água",
        "easy",
        "template",
        "Card de exemplo — pode apagar após importar o modelo.",
        "",
    ]
    flds_str = "\x1f".join(sample_fields)
    sfld_str = sample_fields[0]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        db_file = Path(tmp) / "collection.anki2"
        conn = sqlite3.connect(db_file)
        conn.executescript(ANKI_COLLECTION_SCHEMA)
        conn.execute(
            "INSERT INTO col VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                now_s,
                now_ms,
                now_ms,
                11,
                0,
                0,
                0,
                json.dumps(conf),
                json.dumps(models),
                json.dumps(decks),
                json.dumps(dconf),
                "{}",
            ),
        )
        note_id = now_ms
        card_id = now_ms + 1
        conn.execute(
            "INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (note_id, "janetmpl01", MODEL_ID, now_s, -1, " ", flds_str, sfld_str, _field_checksum(sfld_str), 0, ""),
        )
        conn.execute(
            "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (card_id, note_id, DECK_ID, 0, now_s, -1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, ""),
        )
        conn.commit()
        conn.close()

        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_file, arcname="collection.anki2")
            zf.writestr("media", "{}")

    return out_path
