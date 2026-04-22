"""환경 변수 및 경로 상수 로딩.

P2 원칙 검증: ANTHROPIC_API_KEY 가 설정돼 있으면 즉시 실패한다.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Config:
    dart_api_key: str
    kakao_rest_api_key: str
    kakao_redirect_uri: str
    data_dir: Path
    digests_dir: Path
    db_path: Path
    tokens_path: Path
    ollama_enabled: bool
    ollama_model: str
    public_briefings_dir: Path  # frontend/public/briefings (JSON export 경로)
    vercel_base_url: str        # 카톡 링크 베이스 URL
    edgar_user_agent: str       # SEC EDGAR User-Agent (이름/이메일)


def load_config(project_root: Path | None = None) -> Config:
    root = project_root or PROJECT_ROOT
    env_file = root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

    if os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY 환경 변수가 설정되어 있습니다. "
            "Claude Code가 Max 플랜 대신 API 과금을 사용하게 됩니다 (P2 원칙). "
            "이 변수를 제거한 뒤 다시 실행하세요."
        )

    data_dir = root / "data"
    digests_dir = data_dir / "digests"
    public_briefings_dir = root / "frontend" / "public" / "briefings"
    data_dir.mkdir(parents=True, exist_ok=True)
    digests_dir.mkdir(parents=True, exist_ok=True)
    public_briefings_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        dart_api_key=os.environ.get("DART_API_KEY", ""),
        kakao_rest_api_key=os.environ.get("KAKAO_REST_API_KEY", ""),
        kakao_redirect_uri=os.environ.get(
            "KAKAO_REDIRECT_URI", "http://localhost:8080/callback"
        ),
        data_dir=data_dir,
        digests_dir=digests_dir,
        db_path=data_dir / "briefing.db",
        tokens_path=root / ".kakao_tokens.json",
        ollama_enabled=os.environ.get("OLLAMA_ENABLED", "0") == "1",
        ollama_model=os.environ.get("OLLAMA_MODEL", "qwen2.5:14b"),
        public_briefings_dir=public_briefings_dir,
        vercel_base_url=os.environ.get(
            "VERCEL_BASE_URL", "https://news-briefing.vercel.app"
        ),
        edgar_user_agent=os.environ.get("EDGAR_USER_AGENT", ""),
    )
