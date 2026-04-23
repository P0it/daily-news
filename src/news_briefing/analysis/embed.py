"""임베딩 클라이언트 — Ollama HTTP API 우선, 실패 시 hash fallback.

P2 원칙 준수: OpenAI/기타 유료 embedding API 미사용.
"""
from __future__ import annotations

import hashlib
import logging

import numpy as np
import requests

log = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/embeddings"
_HASH_DIM = 256


def embed_ollama(text: str, *, model: str, timeout: int = 30) -> np.ndarray | None:
    """Ollama embedding API 호출. 실패 시 None."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": text},
            timeout=timeout,
        )
        if resp.status_code != 200:
            log.warning("ollama embed status=%s", resp.status_code)
            return None
        data = resp.json()
        vec = data.get("embedding")
        if not vec:
            return None
        return np.array(vec, dtype=np.float32)
    except Exception as e:
        log.warning("ollama embed 예외: %s", e)
        return None


def embed_hash(text: str) -> np.ndarray:
    """Fallback — 결정적 해시 기반 pseudo-embedding.

    Ollama 미설치 시 파이프라인 동작 보장용. 실제 유사도 품질은 의미없음.
    """
    vec = np.zeros(_HASH_DIM, dtype=np.float32)
    tokens = text.split()
    for tok in tokens:
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % _HASH_DIM
        vec[idx] += 1.0
    n = np.linalg.norm(vec)
    return vec / n if n > 0 else vec


def embed(text: str, *, model: str) -> np.ndarray:
    """Ollama 시도 후 실패 시 hash fallback. 빈 문자열은 zero vector."""
    if not text.strip():
        return np.zeros(_HASH_DIM, dtype=np.float32)
    v = embed_ollama(text, model=model)
    if v is not None:
        return v
    return embed_hash(text)
