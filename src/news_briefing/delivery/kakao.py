"""카카오톡 '나에게 보내기' 전송 + 토큰 관리 (DECISIONS #4, #10)."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)

KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"


@dataclass(frozen=True, slots=True)
class KakaoTokens:
    access_token: str
    refresh_token: str
    expires_at: str | None  # ISO 8601 or None


def load_tokens(path: Path) -> KakaoTokens | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return KakaoTokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=data.get("expires_at"),
    )


def save_tokens(path: Path, tokens: KakaoTokens) -> None:
    path.write_text(
        json.dumps(asdict(tokens), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def refresh_access_token(rest_api_key: str, refresh_token: str) -> KakaoTokens | None:
    try:
        resp = requests.post(
            KAKAO_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": rest_api_key,
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            log.error("kakao refresh 실패 %s: %s", resp.status_code, resp.text)
            return None
        body = resp.json()
        # refresh_token 은 반환되지 않을 수도 있음 (만료 임박 시에만)
        new_refresh = body.get("refresh_token", refresh_token)
        return KakaoTokens(
            access_token=body["access_token"],
            refresh_token=new_refresh,
            expires_at=None,
        )
    except Exception as e:
        log.error("kakao refresh 예외: %s", e)
        return None


def compose_text_template(title: str, url: str, button_title: str = "열기") -> dict:
    return {
        "object_type": "text",
        "text": title,
        "link": {"web_url": url, "mobile_web_url": url},
        "button_title": button_title,
    }


def send_text(
    *, tokens: KakaoTokens, rest_api_key: str, payload: dict, timeout: int = 15
) -> bool:
    try:
        resp = requests.post(
            KAKAO_SEND_URL,
            headers={"Authorization": f"Bearer {tokens.access_token}"},
            data={"template_object": json.dumps(payload, ensure_ascii=False)},
            timeout=timeout,
        )
        if resp.status_code == 200:
            return True
        log.warning("kakao send 응답 status=%s body=%s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        log.error("kakao send 예외: %s", e)
        return False
