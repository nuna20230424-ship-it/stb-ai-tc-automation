"""seed_catalog.py에서 추출한 순수 함수들 — 단위 테스트 가능.

Reference STB·MCP 호출은 seed_catalog.py에 남기고, catalog 필터링/write-back
같은 결정론적 로직만 이 모듈로 분리.
"""
from __future__ import annotations

import json
from pathlib import Path

from .schema import Scenario, dump_catalog


def filter_scenarios(
    scenarios: list[dict],
    *,
    category: str | None = None,
    priority: str | None = None,
    ids: list[str] | None = None,
    missing_only: bool = False,
) -> list[dict]:
    """카탈로그 시드 대상 선별.

    missing_only=True면 `baseline_vector_id`가 비어있는(None/빈문자열) 시나리오만 반환.
    """
    out = scenarios
    if category:
        out = [s for s in out if s["category"].lower() == category.lower()]
    if priority:
        out = [s for s in out if s["priority"] == priority]
    if ids:
        wanted = set(ids)
        out = [s for s in out if s["id"] in wanted]
    if missing_only:
        out = [s for s in out if not s.get("baseline_vector_id")]
    return out


def write_back_catalog(all_scenarios: list[dict], catalog_path: Path) -> None:
    """카탈로그 전체를 pydantic으로 재검증 후 canonical 포맷으로 원자적 저장.

    같은 디렉토리에 .seed.tmp로 쓴 뒤 rename — 중간 인터럽트로부터 보호.
    """
    scenarios = [Scenario.model_validate(item) for item in all_scenarios]
    tmp = catalog_path.with_suffix(catalog_path.suffix + ".seed.tmp")
    dump_catalog(scenarios, tmp)
    tmp.replace(catalog_path)


def count_missing_baselines(scenarios: list[dict]) -> tuple[int, list[str]]:
    """baseline_vector_id 누락 시나리오 수와 ID 리스트 반환."""
    missing = [s["id"] for s in scenarios if not s.get("baseline_vector_id")]
    return len(missing), missing
