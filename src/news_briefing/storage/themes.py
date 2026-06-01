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
    conn.execute(
        "INSERT INTO themes(theme_id, name_ko, description, updated_at) "
        "VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (theme_id) DO UPDATE SET "
        "name_ko=EXCLUDED.name_ko, description=EXCLUDED.description, updated_at=EXCLUDED.updated_at",
        (theme.theme_id, theme.name_ko, theme.description, now),
    )
    conn.commit()


def get_theme(conn: Connection, theme_id: str) -> Theme | None:
    r = conn.execute(
        "SELECT theme_id, name_ko, description FROM themes WHERE theme_id=%s",
        (theme_id,),
    ).fetchone()
    return Theme(r["theme_id"], r["name_ko"], r["description"]) if r else None


def list_themes(conn: Connection) -> list[Theme]:
    rows = conn.execute(
        "SELECT theme_id, name_ko, description FROM themes ORDER BY theme_id"
    ).fetchall()
    return [Theme(r["theme_id"], r["name_ko"], r["description"]) for r in rows]


def upsert_layer(conn: Connection, layer: ValueLayer) -> int:
    """layer 를 upsert (theme_id + name unique). 반환: layer_id."""
    now = datetime.now(UTC).isoformat()
    row = conn.execute(
        "INSERT INTO value_layers(theme_id, name, description, updated_at) "
        "VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (theme_id, name) DO UPDATE SET "
        "description=EXCLUDED.description, updated_at=EXCLUDED.updated_at "
        "RETURNING layer_id",
        (layer.theme_id, layer.name, layer.description, now),
    ).fetchone()
    conn.commit()
    return row["layer_id"]


def list_layers(conn: Connection, theme_id: str) -> list[ValueLayer]:
    rows = conn.execute(
        "SELECT layer_id, theme_id, name, description FROM value_layers "
        "WHERE theme_id=%s ORDER BY layer_id",
        (theme_id,),
    ).fetchall()
    return [
        ValueLayer(r["layer_id"], r["theme_id"], r["name"], r["description"])
        for r in rows
    ]


def upsert_company(conn: Connection, company: CompanyInLayer) -> None:
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO companies_in_layer"
        "(layer_id, ticker, company_name, positioning, verified, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (layer_id, ticker) DO UPDATE SET "
        "company_name=EXCLUDED.company_name, positioning=EXCLUDED.positioning, "
        "verified=EXCLUDED.verified, updated_at=EXCLUDED.updated_at",
        (
            company.layer_id,
            company.ticker,
            company.company_name,
            company.positioning,
            1 if company.verified else 0,
            now,
        ),
    )
    conn.commit()


def list_companies(conn: Connection, layer_id: int) -> list[CompanyInLayer]:
    rows = conn.execute(
        "SELECT layer_id, ticker, company_name, positioning, verified "
        "FROM companies_in_layer WHERE layer_id=%s ORDER BY company_name",
        (layer_id,),
    ).fetchall()
    return [
        CompanyInLayer(
            r["layer_id"],
            r["ticker"],
            r["company_name"],
            r["positioning"],
            bool(r["verified"]),
        )
        for r in rows
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
