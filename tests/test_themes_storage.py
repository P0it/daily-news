from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from news_briefing.storage.db import init_schema
from news_briefing.storage.themes import (
    CompanyInLayer,
    Theme,
    ValueLayer,
    get_theme,
    list_companies,
    list_layers,
    list_themes,
    load_seed,
    upsert_company,
    upsert_layer,
    upsert_theme,
)


def test_upsert_and_get_theme(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    upsert_theme(memory_db, Theme("robotics", "로봇", "산업용·서비스 로봇"))
    got = get_theme(memory_db, "robotics")
    assert got is not None
    assert got.name_ko == "로봇"


def test_list_themes(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    upsert_theme(memory_db, Theme("robotics", "로봇"))
    upsert_theme(memory_db, Theme("ai_semi", "AI 반도체"))
    themes = list_themes(memory_db)
    assert len(themes) == 2


def test_layer_upsert_is_idempotent(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    upsert_theme(memory_db, Theme("robotics", "로봇"))
    lid1 = upsert_layer(
        memory_db, ValueLayer(None, "robotics", "액추에이터", "구 설명")
    )
    lid2 = upsert_layer(
        memory_db, ValueLayer(None, "robotics", "액추에이터", "신 설명")
    )
    assert lid1 == lid2
    layers = list_layers(memory_db, "robotics")
    assert len(layers) == 1
    assert layers[0].description == "신 설명"


def test_company_crud(memory_db: sqlite3.Connection) -> None:
    init_schema(memory_db)
    upsert_theme(memory_db, Theme("robotics", "로봇"))
    lid = upsert_layer(memory_db, ValueLayer(None, "robotics", "액추에이터"))
    upsert_company(
        memory_db,
        CompanyInLayer(
            lid, "058610", "에스피지", "하모닉 감속기 국내 3위", verified=True
        ),
    )
    companies = list_companies(memory_db, lid)
    assert len(companies) == 1
    assert companies[0].verified is True
    assert companies[0].ticker == "058610"


def test_load_seed(memory_db: sqlite3.Connection, tmp_path: Path) -> None:
    init_schema(memory_db)
    seed = {
        "themes": [
            {
                "theme_id": "robotics",
                "name_ko": "로봇",
                "layers": [
                    {
                        "name": "액추에이터",
                        "companies": [
                            {"ticker": "058610", "name": "에스피지"},
                        ],
                    },
                    {
                        "name": "비전센서",
                        "companies": [
                            {"ticker": "148150", "name": "세경하이테크"},
                            {"ticker": "111110", "name": "테스트"},
                        ],
                    },
                ],
            },
            {
                "theme_id": "ai_semi",
                "name_ko": "AI 반도체",
                "layers": [
                    {
                        "name": "HBM",
                        "companies": [
                            {"ticker": "000660", "name": "SK하이닉스"},
                        ],
                    },
                ],
            },
        ]
    }
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
    result = load_seed(memory_db, path)
    assert result == {"robotics": 3, "ai_semi": 1}
    # 재적재 시도 — UPSERT 되어 중복 없어야
    result2 = load_seed(memory_db, path)
    assert result2 == {"robotics": 3, "ai_semi": 1}
    # 여전히 2 테마만
    assert len(list_themes(memory_db)) == 2
