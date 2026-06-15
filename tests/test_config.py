"""Config 로딩·검증 테스트."""
from __future__ import annotations

import pytest

from news_briefing.config import Config, load_config


def test_rejects_anthropic_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """P2 원칙: ANTHROPIC_API_KEY 설정 시 즉시 에러. Max 플랜 대신 API 과금 방지."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-anything")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        load_config()


def test_loads_dart_and_discord_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DART_API_KEY", "dart123")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test")
    cfg = load_config()
    assert cfg.dart_api_key == "dart123"
    assert cfg.discord_webhook_url == "https://discord.com/api/webhooks/test"


def test_missing_dart_key_is_warning_not_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """DART 키는 --dry-run 에선 없이도 동작해야 함."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DART_API_KEY", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    cfg = load_config()
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
        discord_webhook_url="https://discord.com/api/webhooks/test",
        supabase_url="https://example.supabase.co",
        supabase_service_key="svc",
        data_dir=tmp_path,
        digests_dir=tmp_path,
        ollama_enabled=False,
        ollama_model="",
        ollama_embed_model="nomic-embed-text",
        public_briefings_dir=tmp_path / "public",
        vercel_base_url="https://example.com",
        edgar_user_agent="",
        fmp_api_key="",
    )
    with pytest.raises((AttributeError, Exception)):
        cfg.dart_api_key = "z"  # type: ignore[misc]
