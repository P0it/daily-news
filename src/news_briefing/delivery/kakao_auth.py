"""카카오 OAuth 1회성 스크립트.

사용자가 `python -m news_briefing.delivery.kakao_auth` 로 직접 실행한다.
브라우저가 뜨면 카카오 계정으로 로그인하고 '동의'를 누르면,
로컬 HTTP 서버가 콜백 코드를 캐치해 access/refresh 토큰으로 교환한 뒤
`.kakao_tokens.json` 에 저장한다.

사전 조건 (사용자가 카카오 Developers 콘솔에서 직접 해야 함):
  1. 앱 생성 → 앱 설정 > 앱 키 > REST API 키 복사 → `.env` 의 KAKAO_REST_API_KEY 에 입력
  2. 카카오 로그인 ON, Redirect URI 등록: http://localhost:8080/callback
  3. 동의 항목 > 카카오톡 메시지 전송 (talk_message) '사용'
"""
from __future__ import annotations

import logging
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from news_briefing.config import load_config
from news_briefing.delivery.kakao import KAKAO_TOKEN_URL, KakaoTokens, save_tokens

log = logging.getLogger(__name__)

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"


class _CallbackHandler(BaseHTTPRequestHandler):
    captured_code: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/callback":
            qs = urllib.parse.parse_qs(parsed.query)
            code = qs.get("code", [None])[0]
            _CallbackHandler.captured_code = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<h1>인증 완료</h1><p>이 창을 닫고 터미널로 돌아가세요.</p>".encode()
            )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args, **kwargs) -> None:  # 조용히
        return


def run_auth_flow() -> None:
    cfg = load_config()
    if not cfg.kakao_rest_api_key:
        print(
            "KAKAO_REST_API_KEY 가 .env 에 설정돼 있지 않습니다. 먼저 설정하세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    redirect_uri = cfg.kakao_redirect_uri
    authorize_url = (
        f"{KAKAO_AUTHORIZE_URL}"
        f"?client_id={cfg.kakao_rest_api_key}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
        f"&response_type=code"
        f"&scope=talk_message"
    )

    print("브라우저에서 카카오 로그인 페이지를 엽니다.")
    print("로그인 후 '동의하고 계속하기'를 누르세요.")
    print(f"만약 자동으로 열리지 않으면 이 URL을 복사하세요:\n{authorize_url}\n")

    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8080

    webbrowser.open(authorize_url)
    server = HTTPServer((host, port), _CallbackHandler)
    server.handle_request()  # 단 한 번만 받고 종료

    code = _CallbackHandler.captured_code
    if not code:
        print("콜백 code 를 받지 못했습니다.", file=sys.stderr)
        sys.exit(2)

    resp = requests.post(
        KAKAO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": cfg.kakao_rest_api_key,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    tokens = KakaoTokens(
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_at=None,
    )
    save_tokens(cfg.tokens_path, tokens)
    print(f".kakao_tokens.json 저장 완료: {cfg.tokens_path}")


if __name__ == "__main__":
    run_auth_flow()
