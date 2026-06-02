"""Discord 웹훅으로 브리핑 알림 전송."""
from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)


def send_message(webhook_url: str, content: str, timeout: int = 15) -> bool:
    """Discord 웹훅으로 텍스트 메시지를 전송한다. 성공 시 True."""
    try:
        resp = requests.post(
            webhook_url,
            json={"content": content},
            timeout=timeout,
        )
        if resp.status_code in (200, 204):
            return True
        log.warning("discord send 응답 status=%s body=%s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        log.error("discord send 예외: %s", e)
        return False
