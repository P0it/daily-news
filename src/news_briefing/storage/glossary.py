"""용어 해설 (glossary) 테이블 read/write."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    term_id: str
    lang: str
    short_label: str
    explanation: str
    signal_direction: str | None


def get_glossary_entry(
    conn: sqlite3.Connection, term_id: str, lang: str
) -> GlossaryEntry | None:
    row = conn.execute(
        "SELECT term_id, lang, short_label, explanation, signal_direction "
        "FROM glossary WHERE term_id = ? AND lang = ?",
        (term_id, lang),
    ).fetchone()
    if row is None:
        return None
    return GlossaryEntry(
        term_id=row["term_id"],
        lang=row["lang"],
        short_label=row["short_label"],
        explanation=row["explanation"],
        signal_direction=row["signal_direction"],
    )


def upsert_glossary_entry(conn: sqlite3.Connection, entry: GlossaryEntry) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO glossary"
        "(term_id, lang, short_label, explanation, signal_direction, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            entry.term_id,
            entry.lang,
            entry.short_label,
            entry.explanation,
            entry.signal_direction,
            now,
        ),
    )
    conn.commit()
