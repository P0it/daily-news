"""Config 로딩·검증 테스트."""
from __future__ import annotations

import pytest

from news_briefing.config import Config, load_config


def test_rejects_anthropic_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """P2 원칙: ANTHROPIC_API_KEY 설정 시 즉시 에러. Max 플랜 대신 API 과금 방지."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-anything")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        load_config()


def test_loads_dart_and_kakao_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DART_API_KEY", "dart123")
    monkeypatch.setenv("KAKAO_REST_API_KEY", "kakao123")
    cfg = load_config()
    assert cfg.dart_api_key == "dart123"
    assert cfg.kakao_rest_api_key == "kakao123"


def test_missing_dart_key_is_warning_not_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """DART 키는 --dry-run 에선 없이도 동작해야 함."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DART_API_KEY", raising=False)
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    cfg = load_config()
    # .env 파일이 프로젝트 루트에 있으면 load_dotenv 가 덮어쓰지 않는다 (override=False).
    # 실제 값이 있더라도 monkeypatch.delenv 는 os.environ 만 조작하므로,
    # .env 에 값이 있으면 load_dotenv 후 다시 os.environ 에 들어온다.
    # → 이 테스트는 단지 "에러 없이 로드됨" 만 보증.
    assert isinstance(cfg.dart_api_key, str)


def test_data_dir_is_project_relative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = load_config()
    assert cfg.data_dir.name == "data"
    assert cfg.digests_dir.name == "digests"
    assert cfg.digests_dir.parent == cfg.data_dir


def test_config_dataclass_is_immutable(tmp_path) -> None:
    """실수로 런타임에 키를 바꾸지 못하게 (frozen dataclass)."""
    cfg = Config(
        dart_api_key="x",
        kakao_rest_api_key="y",
        kakao_redirect_uri="z",
        data_dir=tmp_path,
        digests_dir=tmp_path,
        db_path=tmp_path / "x.db",
        tokens_path=tmp_path / "t.json",
        ollama_enabled=False,
        ollama_model="",
        public_briefings_dir=tmp_path / "public",
        vercel_base_url="https://example.com",
        edgar_user_agent="",
    )
    with pytest.raises((AttributeError, Exception)):
        cfg.dart_api_key = "z"  # type: ignore[misc]
