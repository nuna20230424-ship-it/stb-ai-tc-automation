"""seed_helpers — filter_scenarios / write_back_catalog / count_missing_baselines."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.catalog.seed_helpers import (
    count_missing_baselines,
    filter_scenarios,
    write_back_catalog,
)


def _make_scenario(sid: str, category: str = "EPG", priority: str = "P1",
                    baseline_id: str | None = None) -> dict:
    """카탈로그 v2 최소 dict — pydantic 검증을 통과하는 형태."""
    return {
        "id": sid,
        "category": category,
        "priority": priority,
        "preconditions": [],
        "steps": [
            {"action": "ir", "key": "POWER"},
            {"action": "capture", "duration": 2},
        ],
        "expected": "예상 화면",
        "sla_ms": 2000,
        "risk_weight": 4 if priority == "P1" else 2,
        "firmware_min": None,
        "firmware_max": None,
        "tags": [f"category:{category.lower()}", "mcp:ir", "mcp:capture"],
        "flake_history": {"runs": 0, "passes": 0, "last_failures": []},
        "owner": None,
        "jira_epic": None,
        "baseline_vector_id": baseline_id,
        "change_signals": [],
        "avg_runtime_sec": None,
        "expected_keywords": [],
    }


# ─── filter_scenarios ──────────────────────────────────────────

def test_filter_missing_only_skips_already_seeded():
    s = [
        _make_scenario("epg_a", baseline_id=None),
        _make_scenario("epg_b", baseline_id="abc-123"),
        _make_scenario("epg_c", baseline_id=""),   # 빈 문자열도 missing 취급
    ]
    out = filter_scenarios(s, missing_only=True)
    assert [x["id"] for x in out] == ["epg_a", "epg_c"]


def test_filter_category_and_priority():
    s = [
        _make_scenario("a", category="EPG", priority="P1"),
        _make_scenario("b", category="OTT", priority="P1"),
        _make_scenario("c", category="EPG", priority="P2"),
    ]
    assert [x["id"] for x in filter_scenarios(s, category="EPG")] == ["a", "c"]
    assert [x["id"] for x in filter_scenarios(s, priority="P1")] == ["a", "b"]
    assert [x["id"] for x in
            filter_scenarios(s, category="EPG", priority="P1")] == ["a"]


def test_filter_ids_intersects_other_filters():
    s = [
        _make_scenario("a", category="EPG", baseline_id=None),
        _make_scenario("b", category="EPG", baseline_id="x"),
        _make_scenario("c", category="OTT", baseline_id=None),
    ]
    out = filter_scenarios(s, ids=["a", "c"], category="EPG")
    assert [x["id"] for x in out] == ["a"]


def test_filter_no_filters_returns_all_unchanged():
    s = [_make_scenario("a"), _make_scenario("b")]
    out = filter_scenarios(s)
    assert out == s


# ─── count_missing_baselines ───────────────────────────────────

def test_count_missing_baselines_returns_ids_in_order():
    s = [
        _make_scenario("a", baseline_id="seeded"),
        _make_scenario("b", baseline_id=None),
        _make_scenario("c", baseline_id=None),
        _make_scenario("d", baseline_id="seeded"),
    ]
    n, ids = count_missing_baselines(s)
    assert n == 2
    assert ids == ["b", "c"]


def test_count_missing_baselines_empty():
    assert count_missing_baselines([]) == (0, [])


# ─── write_back_catalog ────────────────────────────────────────

def test_write_back_round_trip(tmp_path: Path):
    s = [
        _make_scenario("epg_one", baseline_id=None),
        _make_scenario("epg_two", baseline_id="seed-xyz"),
    ]
    catalog = tmp_path / "cat.json"
    catalog.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    # 첫번째 시나리오에 ID 부여 → write-back
    s[0]["baseline_vector_id"] = "newly-seeded-id"
    write_back_catalog(s, catalog)

    reloaded = json.loads(catalog.read_text(encoding="utf-8"))
    assert reloaded[0]["id"] == "epg_one"
    assert reloaded[0]["baseline_vector_id"] == "newly-seeded-id"
    assert reloaded[1]["baseline_vector_id"] == "seed-xyz"


def test_write_back_rejects_invalid_schema(tmp_path: Path):
    """잘못된 시나리오는 pydantic 검증에서 막혀 파일이 깨지지 않아야 함."""
    s = [_make_scenario("good", baseline_id=None)]
    catalog = tmp_path / "cat.json"
    original = json.dumps(s, ensure_ascii=False, indent=2)
    catalog.write_text(original, encoding="utf-8")

    bad = list(s) + [{"id": "X with spaces", "category": "EPG"}]  # 검증 실패
    with pytest.raises(Exception):
        write_back_catalog(bad, catalog)

    # 원본은 그대로
    assert catalog.read_text(encoding="utf-8") == original


def test_write_back_uses_tmp_file_atomically(tmp_path: Path):
    """write_back은 .seed.tmp를 거쳐 rename하므로 호출 후 임시파일이 남지 않는다."""
    s = [_make_scenario("epg_x", baseline_id=None)]
    catalog = tmp_path / "cat.json"
    catalog.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    write_back_catalog(s, catalog)
    assert not (tmp_path / "cat.json.seed.tmp").exists()
