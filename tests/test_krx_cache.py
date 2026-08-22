"""KRX 로컬 파일 캐시 왕복·정책 테스트."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from news_briefing.collectors.krx_market import KrxDaily
from news_briefing.storage import krx_cache


def _sample() -> list[KrxDaily]:
    return [
        KrxDaily(
            bas_dd="20260710",
            code="005930",
            name="삼성전자",
            market="KOSPI",
            sector="",
            close=71000.0,
            change=500.0,
            change_pct=0.71,
            volume=12345678,
            value=900000000000,
            market_cap=420000000000000,
        )
    ]


def test_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(krx_cache, "_CACHE_DIR", tmp_path)
    krx_cache.save_cached_day("20260710", _sample())
    loaded = krx_cache.load_cached_day("20260710")
    assert loaded == _sample()  # frozen dataclass 동등성


def test_miss_returns_none(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(krx_cache, "_CACHE_DIR", tmp_path)
    assert krx_cache.load_cached_day("20260101") is None


def test_empty_not_cached(tmp_path: Path, monkeypatch) -> None:
    """빈 결과(휴장·에러)는 저장하지 않는다 — 일시적 오류가 캐시를 오염시키면 안 됨."""
    monkeypatch.setattr(krx_cache, "_CACHE_DIR", tmp_path)
    krx_cache.save_cached_day("20260710", [])
    assert krx_cache.load_cached_day("20260710") is None


def test_today_not_cached(tmp_path: Path, monkeypatch) -> None:
    """당일치는 장중 미확정이라 저장하지 않는다."""
    monkeypatch.setattr(krx_cache, "_CACHE_DIR", tmp_path)
    today = date.today().strftime("%Y%m%d")
    krx_cache.save_cached_day(today, _sample())
    assert krx_cache.load_cached_day(today) is None


def test_corrupt_cache_falls_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(krx_cache, "_CACHE_DIR", tmp_path)
    (tmp_path / "20260710.json").write_text("{ not json", encoding="utf-8")
    assert krx_cache.load_cached_day("20260710") is None
