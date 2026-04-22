"""증권사 앱 딥링크 생성 (F19).

국내 종목(KRX 6자리 stock_code)만 지원. 해외는 미지원.
주문 실행까지 이동하는 편의 기능일 뿐, 체결은 사용자 손 (CLAUDE.md P1).
"""
from __future__ import annotations


def build_deeplinks(stock_code: str) -> dict[str, str]:
    if not stock_code:
        return {}
    return {
        "toss": f"supertoss://stock/{stock_code}",
        "koreainvestment": f"koreainvestment://stock/{stock_code}",
        "naver": f"https://m.stock.naver.com/domestic/stock/{stock_code}/total",
    }
