"""IR chaos — STB UI를 깨뜨리는 비정상 입력 패턴.

ir-mcp `/send` (POST {codeset, key}) 를 사용. base.run 의 SSH 분기와 달리
HTTP 호출이므로 target 인자는 무관 (ir-mcp 자체가 LAN 어디서나 도달 가능).

패턴:
  - rapid-fire:        같은 키를 `count` 회 짧은 간격으로
  - invalid-sequence:  존재하지 않는 키 이름 시도 (404 응답 누적)
  - conflict:          상충 키 동시 (예: UP+DOWN, MENU+BACK)
  - reentry-storm:     MENU → BACK → MENU → BACK ... 빠른 토글
"""
from __future__ import annotations

import os
import time
from typing import Iterable

import httpx

from .base import AnomalyError

DEFAULT_CODESET = os.getenv("IR_CODESET", "android_tv")
DEFAULT_IR_MCP = os.getenv("IR_MCP_URL", "http://localhost:8002")
DEFAULT_INTERVAL_MS = 30


_KNOWN_PATTERNS = ("rapid-fire", "invalid-sequence", "conflict", "reentry-storm")


def _send_one(client: httpx.Client, codeset: str, key: str) -> int:
    """ir-mcp /send 1회 호출. HTTP status code 반환 (404/500도 그대로)."""
    try:
        resp = client.post("/send", json={"codeset": codeset, "key": key}, timeout=3.0)
    except httpx.HTTPError as e:
        raise AnomalyError(f"ir-mcp unreachable: {e}") from e
    return resp.status_code


def _sequence_for(pattern: str, key: str, count: int) -> list[str]:
    if pattern == "rapid-fire":
        return [key] * count
    if pattern == "invalid-sequence":
        return [f"NONEXISTENT_{i}" for i in range(count)]
    if pattern == "conflict":
        pairs = [("UP", "DOWN"), ("LEFT", "RIGHT"), ("MENU", "BACK"), ("PLAY", "STOP")]
        flat: list[str] = []
        for i in range(count):
            a, b = pairs[i % len(pairs)]
            flat.extend([a, b])
        return flat
    if pattern == "reentry-storm":
        return [("MENU" if i % 2 == 0 else "BACK") for i in range(count)]
    raise AnomalyError(f"unknown pattern: {pattern!r}. one of: {_KNOWN_PATTERNS}")


def ir_chaos(
    pattern: str = "rapid-fire",
    *,
    key: str = "OK",
    count: int = 50,
    interval_ms: int = DEFAULT_INTERVAL_MS,
    codeset: str = DEFAULT_CODESET,
    ir_mcp_url: str = DEFAULT_IR_MCP,
    dry_run: bool = False,
    client: httpx.Client | None = None,
) -> dict:
    """IR chaos 패턴 실행. 호출 통계 dict 반환.

    Args:
        pattern: rapid-fire / invalid-sequence / conflict / reentry-storm.
        key:     rapid-fire 일 때만 의미 (그 외 패턴은 자체 키 시퀀스 사용).
        count:   send 호출 횟수.
        interval_ms: 키 사이 간격.
        codeset: ir-mcp 코드셋 이름.
        client:  테스트용 주입 (httpx.Client). None 이면 새로 만듦.
    """
    if pattern not in _KNOWN_PATTERNS:
        raise AnomalyError(f"unknown pattern: {pattern!r}. one of: {_KNOWN_PATTERNS}")
    if count <= 0:
        raise AnomalyError(f"count 는 양수여야 합니다: {count}")

    seq = _sequence_for(pattern, key, count)

    if dry_run:
        return {
            "pattern": pattern, "codeset": codeset, "ir_mcp_url": ir_mcp_url,
            "sent": 0, "ok": 0, "errors": 0, "dry_run": True,
            "preview": seq[:5] + (["…"] if len(seq) > 5 else []),
        }

    own_client = client is None
    cli = client or httpx.Client(base_url=ir_mcp_url)
    ok = 0
    errors = 0
    try:
        for k in seq:
            status = _send_one(cli, codeset, k)
            if 200 <= status < 300:
                ok += 1
            else:
                errors += 1
            if interval_ms > 0:
                time.sleep(interval_ms / 1000)
    finally:
        if own_client:
            cli.close()

    return {
        "pattern": pattern, "codeset": codeset, "ir_mcp_url": ir_mcp_url,
        "sent": len(seq), "ok": ok, "errors": errors,
    }


def known_patterns() -> Iterable[str]:
    return _KNOWN_PATTERNS
