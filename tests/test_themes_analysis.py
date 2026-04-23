from __future__ import annotations

from news_briefing.analysis.themes import (
    decompose_theme,
    generate_positioning,
    refresh_theme_layers,
)
from news_briefing.storage.db import init_schema
from news_briefing.storage.themes import Theme, list_layers, upsert_theme


def test_decompose_theme_parses_json(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        return_value='{"layers": [{"name": "액추에이터"}], "caveats": "..."}',
    )
    result = decompose_theme("로봇")
    assert result is not None
    assert result["layers"][0]["name"] == "액추에이터"


def test_decompose_handles_code_fences(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        return_value='```json\n{"layers": []}\n```',
    )
    result = decompose_theme("로봇")
    assert result == {"layers": []}


def test_decompose_returns_none_on_llm_failure(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        side_effect=RuntimeError("boom"),
    )
    assert decompose_theme("x") is None


def test_decompose_returns_none_on_invalid_json(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        return_value="not json at all",
    )
    assert decompose_theme("x") is None


def test_generate_positioning_calls_llm(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        return_value="하모닉 감속기 국내 3위 포지션이에요.",
    )
    result = generate_positioning(
        company_name="에스피지", ticker="058610", layer="액추에이터"
    )
    assert "하모닉" in result


def test_generate_positioning_returns_none_on_failure(mocker) -> None:
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        side_effect=RuntimeError("boom"),
    )
    assert generate_positioning(
        company_name="x", ticker="000000", layer="y"
    ) is None


def test_refresh_theme_layers_writes_to_db(memory_db, mocker) -> None:
    init_schema(memory_db)
    upsert_theme(memory_db, Theme("robotics", "로봇"))
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        return_value=(
            '{"layers": ['
            '{"name": "액추에이터", "description": "모터·감속기"},'
            '{"name": "제어 AI", "description": "소프트웨어"}'
            '], "caveats": ""}'
        ),
    )
    n = refresh_theme_layers(memory_db, Theme("robotics", "로봇"))
    assert n == 2
    layers = list_layers(memory_db, "robotics")
    assert len(layers) == 2
    names = {lay.name for lay in layers}
    assert names == {"액추에이터", "제어 AI"}


def test_refresh_theme_layers_returns_zero_on_llm_failure(
    memory_db, mocker
) -> None:
    init_schema(memory_db)
    upsert_theme(memory_db, Theme("x", "X"))
    mocker.patch(
        "news_briefing.analysis.themes._call_claude",
        side_effect=RuntimeError("boom"),
    )
    assert refresh_theme_layers(memory_db, Theme("x", "X")) == 0
