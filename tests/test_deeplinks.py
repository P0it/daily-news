from __future__ import annotations

from news_briefing.delivery.deeplinks import build_deeplinks


def test_samsung_links() -> None:
    links = build_deeplinks("005930")
    assert links["toss"] == "supertoss://stock/005930"
    assert links["koreainvestment"].endswith("005930")
    assert "005930" in links["naver"]


def test_empty_code_returns_empty_dict() -> None:
    assert build_deeplinks("") == {}


def test_all_three_providers_present() -> None:
    links = build_deeplinks("000660")
    assert set(links.keys()) == {"toss", "koreainvestment", "naver"}
