"""테마·밸류체인 DB CRUD + seed loader (ARCHITECTURE.md 5.4)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from news_briefing.storage.db import Connection


@dataclass(frozen=True, slots=True)
class Theme:
    theme_id: str
    name_ko: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ValueLayer:
    layer_id: int | None  # None before insert
    theme_id: str
    name: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class CompanyInLayer:
    layer_id: int
    ticker: str
    company_name: str
    positioning: str | None = None
    verified: bool = False


def upsert_theme(conn: Connection, theme: Theme) -> None:
    now = datetime.now(UTC).isoformat()
    conn.table("themes").upsert({
        "theme_id": theme.theme_id,
        "name_ko": theme.name_ko,
        "description": theme.description,
        "updated_at": now,
    }).execute()


def get_theme(conn: Connection, theme_id: str) -> Theme | None:
    r = (
        conn.table("themes")
        .select("theme_id,name_ko,description")
        .eq("theme_id", theme_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    d = r.data[0]
    return Theme(d["theme_id"], d["name_ko"], d["description"])


def list_themes(conn: Connection) -> list[Theme]:
    r = conn.table("themes").select("theme_id,name_ko,description").order("theme_id").execute()
    return [Theme(d["theme_id"], d["name_ko"], d["description"]) for d in r.data]


def upsert_layer(conn: Connection, layer: ValueLayer) -> int:
    """layer 를 upsert (theme_id + name unique). 반환: layer_id."""
    now = datetime.now(UTC).isoformat()
    r = (
        conn.table("value_layers")
        .upsert(
            {
                "theme_id": layer.theme_id,
                "name": layer.name,
                "description": layer.description,
                "updated_at": now,
            },
            on_conflict="theme_id,name",
        )
        .execute()
    )
    return int(r.data[0]["layer_id"])


def list_layers(conn: Connection, theme_id: str) -> list[ValueLayer]:
    r = (
        conn.table("value_layers")
        .select("layer_id,theme_id,name,description")
        .eq("theme_id", theme_id)
        .order("layer_id")
        .execute()
    )
    return [
        ValueLayer(d["layer_id"], d["theme_id"], d["name"], d["description"])
        for d in r.data
    ]


def upsert_company(conn: Connection, company: CompanyInLayer) -> None:
    now = datetime.now(UTC).isoformat()
    conn.table("companies_in_layer").upsert({
        "layer_id": company.layer_id,
        "ticker": company.ticker,
        "company_name": company.company_name,
        "positioning": company.positioning,
        "verified": 1 if company.verified else 0,
        "updated_at": now,
    }).execute()


def list_companies(conn: Connection, layer_id: int) -> list[CompanyInLayer]:
    r = (
        conn.table("companies_in_layer")
        .select("layer_id,ticker,company_name,positioning,verified")
        .eq("layer_id", layer_id)
        .order("company_name")
        .execute()
    )
    return [
        CompanyInLayer(
            d["layer_id"],
            d["ticker"],
            d["company_name"],
            d["positioning"],
            bool(d["verified"]),
        )
        for d in r.data
    ]


def load_seed(conn: Connection, seed_path: Path) -> dict[str, int]:
    """seed JSON 을 DB 에 일괄 적재. 반환: {theme_id: company_count}."""
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    result: dict[str, int] = {}
    for theme_data in data.get("themes", []):
        theme = Theme(
            theme_id=theme_data["theme_id"],
            name_ko=theme_data["name_ko"],
            description=theme_data.get("description"),
        )
        upsert_theme(conn, theme)
        cnt = 0
        for layer_data in theme_data.get("layers", []):
            lid = upsert_layer(
                conn,
                ValueLayer(
                    None,
                    theme.theme_id,
                    layer_data["name"],
                    layer_data.get("description"),
                ),
            )
            for c in layer_data.get("companies", []):
                upsert_company(
                    conn,
                    CompanyInLayer(
                        layer_id=lid,
                        ticker=c["ticker"],
                        company_name=c["name"],
                        positioning=c.get("positioning"),
                        verified=bool(c.get("verified", False)),
                    ),
                )
                cnt += 1
        result[theme.theme_id] = cnt
    return result
