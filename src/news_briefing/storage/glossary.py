"""용어 해설 (glossary) 테이블 read/write."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from news_briefing.storage.db import Connection


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    term_id: str
    lang: str
    short_label: str
    explanation: str
    signal_direction: str | None


def get_glossary_entry(conn: Connection, term_id: str, lang: str) -> GlossaryEntry | None:
    row = conn.execute(
        "SELECT term_id, lang, short_label, explanation, signal_direction "
        "FROM glossary WHERE term_id = %s AND lang = %s",
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


def upsert_glossary_entry(conn: Connection, entry: GlossaryEntry) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO glossary"
        "(term_id, lang, short_label, explanation, signal_direction, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (term_id, lang) DO UPDATE SET "
        "short_label=EXCLUDED.short_label, explanation=EXCLUDED.explanation, "
        "signal_direction=EXCLUDED.signal_direction, updated_at=EXCLUDED.updated_at",
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
