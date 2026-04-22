from __future__ import annotations

from news_briefing.analysis.scoring import score_edgar


def test_form4_base_score() -> None:
    score, direction = score_edgar(form_type="4", items="")
    assert score == 70
    assert direction == "mixed"


def test_8k_item_1_01_material_agreement() -> None:
    """Item 1.01 — Material Definitive Agreement."""
    score, direction = score_edgar(form_type="8-K", items="1.01")
    assert score == 75
    assert direction == "positive"


def test_8k_item_2_01_acquisition() -> None:
    """Item 2.01 — Completion of Acquisition / Disposition."""
    score, direction = score_edgar(form_type="8-K", items="2.01")
    assert score == 85
    assert direction == "mixed"


def test_8k_item_2_06_impairment() -> None:
    """Item 2.06 — Material Impairments (부정)."""
    score, direction = score_edgar(form_type="8-K", items="2.06")
    assert score == 95
    assert direction == "negative"


def test_8k_item_4_02_restated_financials() -> None:
    """Item 4.02 — Non-reliance on previously issued financials."""
    score, direction = score_edgar(form_type="8-K", items="4.02")
    assert score == 90
    assert direction == "negative"


def test_8k_unknown_item_defaults_to_base() -> None:
    score, direction = score_edgar(form_type="8-K", items="")
    assert score == 70
    assert direction == "neutral"


def test_non_4_or_8k_form_falls_to_low_score() -> None:
    score, direction = score_edgar(form_type="10-Q", items="")
    assert score == 45
    assert direction == "neutral"
