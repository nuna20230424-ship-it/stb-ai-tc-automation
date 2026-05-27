"""Flake 점수 + quarantine 판정 + flake_history 갱신 (순수 함수).

flake_history 스키마 (catalog v2):
  {"runs": int, "passes": int, "last_failures": [ISO ts, ...]}
"""
from __future__ import annotations

from datetime import datetime, timezone


def pass_rate(flake_history: dict) -> float:
    runs = flake_history.get("runs", 0)
    if not runs:
        return 1.0
    return flake_history.get("passes", 0) / runs


def flake_score(flake_history: dict) -> float:
    """0.0(안정) ~ 1.0(완전 불안정). 단순히 실패율."""
    return round(1.0 - pass_rate(flake_history), 4)


def should_quarantine(
    flake_history: dict,
    *,
    min_runs: int = 10,
    max_fail_rate: float = 0.30,
) -> bool:
    """충분히 돌렸는데(min_runs↑) 실패율이 임계를 넘으면 격리.

    Atlassian/Google 표준: 자동 격리 + 재시도 + 점수 추적.
    """
    runs = flake_history.get("runs", 0)
    if runs < min_runs:
        return False
    return (1.0 - pass_rate(flake_history)) > max_fail_rate


def quarantine_list(
    scenarios: list[dict],
    *,
    min_runs: int = 10,
    max_fail_rate: float = 0.30,
) -> list[dict]:
    """격리 대상 시나리오 + 사유 반환."""
    out: list[dict] = []
    for s in scenarios:
        fh = s.get("flake_history", {}) or {}
        if should_quarantine(fh, min_runs=min_runs, max_fail_rate=max_fail_rate):
            out.append({
                "id": s["id"],
                "category": s.get("category"),
                "runs": fh.get("runs", 0),
                "pass_rate": round(pass_rate(fh), 4),
                "flake_score": flake_score(fh),
            })
    return out


def update_flake_history(
    flake_history: dict,
    passed: bool,
    *,
    now: datetime | None = None,
    keep_failures: int = 10,
) -> dict:
    """1회 실행 결과를 반영한 새 flake_history 반환 (원본 불변)."""
    fh = {
        "runs": flake_history.get("runs", 0) + 1,
        "passes": flake_history.get("passes", 0) + (1 if passed else 0),
        "last_failures": list(flake_history.get("last_failures", [])),
    }
    if not passed:
        ts = (now or datetime.now(timezone.utc)).isoformat()
        fh["last_failures"].append(ts)
        fh["last_failures"] = fh["last_failures"][-keep_failures:]
    return fh
