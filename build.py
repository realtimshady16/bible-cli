#!/usr/bin/env python3
"""Build a local, searchable Bible database.

Sources (both public domain):
  data/kjv.json          scrollmapper/bible_databases KJV
  data/eng-web_usfm.zip  ebible.org World English Bible (USFM)

Output: ~/.local/share/bible/bible.db (SQLite + FTS5)

Run: ./build.py
"""

import json
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DB = Path.home() / ".local/share/bible/bible.db"

BOOKS = [
    ("Gen", "Genesis"), ("Exod", "Exodus"), ("Lev", "Leviticus"), ("Num", "Numbers"),
    ("Deut", "Deuteronomy"), ("Josh", "Joshua"), ("Judg", "Judges"), ("Ruth", "Ruth"),
    ("1Sam", "1 Samuel"), ("2Sam", "2 Samuel"), ("1Kgs", "1 Kings"), ("2Kgs", "2 Kings"),
    ("1Chr", "1 Chronicles"), ("2Chr", "2 Chronicles"), ("Ezra", "Ezra"), ("Neh", "Nehemiah"),
    ("Esth", "Esther"), ("Job", "Job"), ("Ps", "Psalms"), ("Prov", "Proverbs"),
    ("Eccl", "Ecclesiastes"), ("Song", "Song of Solomon"), ("Isa", "Isaiah"), ("Jer", "Jeremiah"),
    ("Lam", "Lamentations"), ("Ezek", "Ezekiel"), ("Dan", "Daniel"), ("Hos", "Hosea"),
    ("Joel", "Joel"), ("Amos", "Amos"), ("Obad", "Obadiah"), ("Jonah", "Jonah"),
    ("Mic", "Micah"), ("Nah", "Nahum"), ("Hab", "Habakkuk"), ("Zeph", "Zephaniah"),
    ("Hag", "Haggai"), ("Zech", "Zechariah"), ("Mal", "Malachi"),
    ("Matt", "Matthew"), ("Mark", "Mark"), ("Luke", "Luke"), ("John", "John"),
    ("Acts", "Acts"), ("Rom", "Romans"), ("1Cor", "1 Corinthians"), ("2Cor", "2 Corinthians"),
    ("Gal", "Galatians"), ("Eph", "Ephesians"), ("Phil", "Philippians"), ("Col", "Colossians"),
    ("1Thess", "1 Thessalonians"), ("2Thess", "2 Thessalonians"), ("1Tim", "1 Timothy"),
    ("2Tim", "2 Timothy"), ("Titus", "Titus"), ("Phlm", "Philemon"), ("Heb", "Hebrews"),
    ("Jas", "James"), ("1Pet", "1 Peter"), ("2Pet", "2 Peter"), ("1John", "1 John"),
    ("2John", "2 John"), ("3John", "3 John"), ("Jude", "Jude"), ("Rev", "Revelation"),
]
ORDER = {code: i for i, (code, _name) in enumerate(BOOKS, start=1)}
NAME = dict(BOOKS)

USFM_TO_CODE = {
    "GEN": "Gen", "EXO": "Exod", "LEV": "Lev", "NUM": "Num", "DEU": "Deut", "JOS": "Josh",
    "JDG": "Judg", "RUT": "Ruth", "1SA": "1Sam", "2SA": "2Sam", "1KI": "1Kgs", "2KI": "2Kgs",
    "1CH": "1Chr", "2CH": "2Chr", "EZR": "Ezra", "NEH": "Neh", "EST": "Esth", "JOB": "Job",
    "PSA": "Ps", "PRO": "Prov", "ECC": "Eccl", "SNG": "Song", "ISA": "Isa", "JER": "Jer",
    "LAM": "Lam", "EZK": "Ezek", "DAN": "Dan", "HOS": "Hos", "JOL": "Joel", "AMO": "Amos",
    "OBA": "Obad", "JON": "Jonah", "MIC": "Mic", "NAM": "Nah", "HAB": "Hab", "ZEP": "Zeph",
    "HAG": "Hag", "ZEC": "Zech", "MAL": "Mal", "MAT": "Matt", "MRK": "Mark", "LUK": "Luke",
    "JHN": "John", "ACT": "Acts", "ROM": "Rom", "1CO": "1Cor", "2CO": "2Cor", "GAL": "Gal",
    "EPH": "Eph", "PHP": "Phil", "COL": "Col", "1TH": "1Thess", "2TH": "2Thess", "1TI": "1Tim",
    "2TI": "2Tim", "TIT": "Titus", "PHM": "Phlm", "HEB": "Heb", "JAS": "Jas", "1PE": "1Pet",
    "2PE": "2Pet", "1JN": "1John", "2JN": "2John", "3JN": "3John", "JUD": "Jude", "REV": "Rev",
}

# Normalise the KJV book names to our codes.
KJV_NAMES = {
    "psalm": "Ps", "song of solomon": "Song", "revelation": "Rev", "1 samuel": "1Sam",
    "2 samuel": "2Sam", "1 kings": "1Kgs", "2 kings": "2Kgs", "1 chronicles": "1Chr",
    "2 chronicles": "2Chr", "1 corinthians": "1Cor", "2 corinthians": "2Cor",
    "1 thessalonians": "1Thess", "2 thessalonians": "2Thess", "1 timothy": "1Tim",
    "2 timothy": "2Tim", "1 peter": "1Pet", "2 peter": "2Pet", "1 john": "1John",
    "2 john": "2John", "3 john": "3John",
}


ROMAN = {"iii": "3", "ii": "2", "i": "1"}


def kjv_code(name: str) -> str:
    key = name.strip().lower()
    first, _, rest = key.partition(" ")
    if first in ROMAN:
        key = f"{ROMAN[first]} {rest}"
    if key in KJV_NAMES:
        return KJV_NAMES[key]
    for code, full in BOOKS:
        if full.lower() == key:
            return code
    raise KeyError(f"unknown KJV book: {name}")


FOOTNOTE = re.compile(r"\\(f|x|fig)\b.*?\\(f|x|fig)\*", re.S)
MILESTONE_WORD = re.compile(r"\\\+?w\s+([^|\\]*?)\|[^\\]*?\\\+?w\*", re.S)
CHAR_STYLE = re.compile(r"\\\+?(add|nd|wj|qt|bk|it|bd|em|sc|sup|no|ord|pn|k|tl|sls|sig|fm|va|vp|ca|cl|cp|fig)\b\s*(.*?)\\\+?\1\*", re.S)
INLINE_CMD = re.compile(r"\\\+?[a-z0-9]+\*?")
WHITESPACE = re.compile(r"\s+")


def clean_usfm(text: str) -> str:
    text = FOOTNOTE.sub("", text)
    text = MILESTONE_WORD.sub(r"\1 ", text)
    for _ in range(3):
        text = CHAR_STYLE.sub(r"\2", text)
    text = INLINE_CMD.sub("", text)
    text = text.replace("\\", "")
    text = WHITESPACE.sub(" ", text).strip()
    # Milestone markers leave spaces before punctuation ("world , that").
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([\u201c\u2018])\s+", r"\1", text)
    text = re.sub(r"\s+([\u201d\u2019])", r"\1", text)
    return text.strip()


def parse_kjv():
    payload = json.loads((DATA / "kjv.json").read_text(encoding="utf-8"))
    books = payload["books"]
    if len(books) != len(BOOKS):
        raise SystemExit(f"expected {len(BOOKS)} KJV books, found {len(books)}")
    # The file lists exactly the Protestant canon in order, so position is a
    # more reliable key than the names ("Revelation of John", "I Samuel").
    for index, book in enumerate(books):
        code = BOOKS[index][0]
        for chapter in book["chapters"]:
            number = int(chapter["chapter"])
            for verse in chapter["verses"]:
                text = WHITESPACE.sub(" ", verse["text"]).strip()
                if text:
                    yield ("kjv", code, number, int(verse["verse"]), text)


def parse_web():
    with zipfile.ZipFile(DATA / "eng-web_usfm.zip") as archive:
        for name in archive.namelist():
            if not name.endswith(".usfm"):
                continue
            raw = archive.read(name).decode("utf-8", errors="replace")
            ident = re.search(r"^\\id\s+([A-Z0-9]{3})", raw, re.M)
            if not ident:
                continue
            code = USFM_TO_CODE.get(ident.group(1).upper())
            if not code:
                continue  # apocrypha or front matter
            chapter = None
            for line in raw.splitlines():
                stripped = line.strip()
                if stripped.startswith("\\c "):
                    try:
                        chapter = int(stripped[3:].strip().split()[0])
                    except (ValueError, IndexError):
                        chapter = None
                    continue
                if chapter is None or not stripped.startswith("\\v "):
                    continue
                match = re.match(r"\\v\s+(\d+)\s*(.*)$", stripped, re.S)
                if not match:
                    continue
                text = clean_usfm(match.group(2))
                if text:
                    yield ("web", code, chapter, int(match.group(1)), text)


def build():
    if not (DATA / "kjv.json").is_file() or not (DATA / "eng-web_usfm.zip").is_file():
        sys.exit("missing source files in data/ — see README")
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
        DROP TABLE IF EXISTS verses;
        DROP TABLE IF EXISTS verses_fts;
        DROP TABLE IF EXISTS books;
        CREATE TABLE books (
            translation TEXT, code TEXT, name TEXT, testament TEXT, ord INTEGER,
            PRIMARY KEY (translation, code)
        );
        CREATE TABLE verses (
            id INTEGER PRIMARY KEY,
            translation TEXT, code TEXT, chapter INTEGER, verse INTEGER, text TEXT
        );
        CREATE VIRTUAL TABLE verses_fts USING fts5(
            text, content='verses', content_rowid='id', tokenize='porter unicode61'
        );
        CREATE INDEX verse_ref ON verses(translation, code, chapter, verse);
    """)
    for translation in ("kjv", "web"):
        con.executemany(
            "INSERT INTO books VALUES (?,?,?,?,?)",
            [(translation, code, name, "OT" if ORDER[code] <= 39 else "NT", ORDER[code])
             for code, name in BOOKS],
        )
    rows = []
    rows.extend(parse_kjv())
    rows.extend(parse_web())
    con.executemany(
        "INSERT INTO verses (translation, code, chapter, verse, text) VALUES (?,?,?,?,?)", rows
    )
    con.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild')")
    con.commit()
    counts = con.execute(
        "SELECT translation, count(*) FROM verses GROUP BY translation"
    ).fetchall()
    print(f"built {DB}")
    for translation, count in counts:
        print(f"  {translation}: {count:,} verses")


if __name__ == "__main__":
    build()
