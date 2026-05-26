"""Grafana provisioning JSON 구조 회귀 방지.

provisioning 디렉토리의 모든 dashboard JSON이:
  - 유효한 JSON
  - 필수 키 (uid/title/schemaVersion/panels) 보유
  - 비-row 패널마다 datasource + targets[].query 보유
  - judge-pipeline dashboard는 docs/29의 3개 핵심 패널 카테고리(tier / gray zone / confidence)를 모두 포함
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = (
    REPO_ROOT / "infrastructure" / "mac-mini-backend"
    / "grafana" / "provisioning" / "dashboards"
)


def _dashboard_paths() -> list[Path]:
    return sorted(DASHBOARD_DIR.glob("*.json"))


@pytest.mark.parametrize("path", _dashboard_paths(), ids=lambda p: p.name)
def test_dashboard_is_well_formed(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    for key in ("uid", "title", "schemaVersion", "panels"):
        assert key in d, f"{path.name} missing top-level key: {key}"
    assert isinstance(d["panels"], list) and d["panels"], f"{path.name} has no panels"

    for panel in d["panels"]:
        if panel.get("type") == "row":
            continue
        pid = panel.get("id")
        assert panel.get("datasource"), f"{path.name} panel #{pid} missing datasource"
        targets = panel.get("targets") or []
        assert targets, f"{path.name} panel #{pid} has no targets"
        for t in targets:
            assert t.get("query"), f"{path.name} panel #{pid} target missing query"


def test_judge_pipeline_covers_three_required_categories():
    path = DASHBOARD_DIR / "stb-judge-pipeline.json"
    d = json.loads(path.read_text(encoding="utf-8"))

    titles = " ".join(p["title"] for p in d["panels"] if p.get("type") != "row")
    # 사용자 요구 3종: tier 분포 / 회색 지대 비율 / 카테고리별 confidence
    assert "Tier" in titles or "tier" in titles
    assert "Gray Zone" in titles or "회색 지대" in titles
    assert "Confidence" in titles or "confidence" in titles


def test_judge_pipeline_queries_target_catalog_runs():
    """모든 데이터 패널이 catalog_runs measurement를 조회해야 한다."""
    path = DASHBOARD_DIR / "stb-judge-pipeline.json"
    d = json.loads(path.read_text(encoding="utf-8"))

    for panel in d["panels"]:
        if panel.get("type") == "row":
            continue
        for t in panel["targets"]:
            assert 'r._measurement == "catalog_runs"' in t["query"], (
                f"panel #{panel['id']} doesn't query catalog_runs: {t['query'][:80]}"
            )


def test_judge_pipeline_filters_by_template_vars():
    """모든 데이터 쿼리가 $category / $priority 템플릿 변수로 필터링되어야 한다."""
    path = DASHBOARD_DIR / "stb-judge-pipeline.json"
    d = json.loads(path.read_text(encoding="utf-8"))

    for panel in d["panels"]:
        if panel.get("type") == "row":
            continue
        for t in panel["targets"]:
            q = t["query"]
            assert "${category:json}" in q, f"panel #{panel['id']} missing $category filter"
            assert "${priority:json}" in q, f"panel #{panel['id']} missing $priority filter"


def test_dashboard_uids_are_unique():
    """provisioning이 충돌 없이 등록되려면 UID 유일해야 한다."""
    uids = [json.loads(p.read_text(encoding="utf-8"))["uid"] for p in _dashboard_paths()]
    assert len(uids) == len(set(uids)), f"duplicate UIDs: {uids}"
