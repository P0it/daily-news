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
    r = (
        conn.table("glossary")
        .select("term_id,lang,short_label,explanation,signal_direction")
        .eq("term_id", term_id)
        .eq("lang", lang)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    d = r.data[0]
    return GlossaryEntry(
        term_id=d["term_id"],
        lang=d["lang"],
        short_label=d["short_label"],
        explanation=d["explanation"],
        signal_direction=d["signal_direction"],
    )


def upsert_glossary_entry(conn: Connection, entry: GlossaryEntry) -> None:
    now = datetime.now(UTC).isoformat()
    conn.table("glossary").upsert({
        "term_id": entry.term_id,
        "lang": entry.lang,
        "short_label": entry.short_label,
        "explanation": entry.explanation,
        "signal_direction": entry.signal_direction,
        "updated_at": now,
    }).execute()
