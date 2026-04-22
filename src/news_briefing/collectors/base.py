"""수집기 공통 타입."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ItemKind = Literal["disclosure", "news"]


@dataclass(frozen=True, slots=True)
class CollectedItem:
    source: str                       # 'dart', 'rss:hankyung' 등
    ext_id: str                       # DART rcept_no, RSS guid
    kind: ItemKind
    title: str
    url: str
    published_at: datetime
    body: str = ""                    # 추가 본문 (없어도 됨)
    company: str = ""                 # 해당되는 경우
    company_code: str = ""            # 종목코드 (DART 의 경우 stock_code)
    extra: dict[str, Any] = field(default_factory=dict)
