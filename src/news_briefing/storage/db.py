"""Supabase 클라이언트 (supabase-py, REST API 경유).

psycopg2 직접 TCP 연결 대신 HTTPS REST API를 사용하여 IPv6 전용 환경에서도 동작한다.
storage 모듈은 Connection 타입을 import해서 사용하며, 실제 구현은 supabase Client다.
"""
from __future__ import annotations

import logging
from typing import Any

from supabase import Client, create_client

log = logging.getLogger(__name__)


class Connection:
    """supabase Client 래퍼.

    storage 모듈 전체가 conn: Connection 타입으로 주입받는다.
    conn.table(...) 호출은 supabase Client로 위임하고,
    conn.close()는 HTTP 클라이언트가 관리하므로 no-op.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def close(self) -> None:
        pass


def get_client(supabase_url: str, service_key: str) -> Connection:
    """service_role 키로 Supabase 클라이언트 생성.

    HTTP/2 는 Windows에서 WinError 10054 연결 재설정이 발생하므로 HTTP/1.1 강제.
    """
    import httpx

    client = create_client(supabase_url, service_key)
    # postgrest session 을 HTTP/1.1 전용 + 연결 재사용 없음으로 교체
    # WinError 10054 (연결 재설정) 방지: keep-alive 풀 비활성화
    old_session = client.postgrest.session
    client.postgrest.session = httpx.Client(
        http2=False,
        headers=dict(old_session.headers),
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
    )
    return Connection(client)


# 하위 호환 — orchestrator / cli 의 connect(cfg.database_url) 호출을 위해 유지
# 실제 연결은 get_client() 로 대체되어야 한다.
def connect(database_url: str) -> Connection:  # noqa: ARG001
    raise RuntimeError(
        "connect(database_url) 는 더 이상 사용하지 않습니다. "
        "get_client(supabase_url, service_key) 를 사용하세요."
    )
