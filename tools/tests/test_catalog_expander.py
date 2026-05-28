"""catalog_expander — expander 순수 함수 + 실제 param_spec 검증."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.catalog.schema import Scenario, infer_defaults
from tools.catalog_expander.expander import (
    _subst,
    _subst_str,
    check_collisions,
    expand_all,
    expand_family,
)

SPEC_PATH = Path(__file__).resolve().parents[1] / "catalog_expander" / "param_spec.json"
CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"
)


# ──────────────── 치환 ────────────────

def test_subst_str_full_placeholder_preserves_type():
    assert _subst_str("{taps}", {"taps": 3}) == 3       # int 보존
    assert _subst_str("{name}", {"name": "KBS1"}) == "KBS1"


def test_subst_str_embedded():
    assert _subst_str("{name} 채널", {"name": "MBC"}) == "MBC 채널"


def test_subst_str_missing_key_keeps_placeholder():
    assert _subst_str("{unknown}", {}) == "{unknown}"


def test_subst_recursive():
    obj = {"action": "ir", "key": "{key}", "nested": ["{a}", {"x": "{b}"}]}
    out = _subst(obj, {"key": "OK", "a": "1", "b": "2"})
    assert out == {"action": "ir", "key": "OK", "nested": ["1", {"x": "2"}]}


# ──────────────── expand_family ────────────────

def _family():
    return {
        "id_template": "epg_zap_{slug}",
        "category": "EPG",
        "priority": "{priority}",
        "preconditions": ["live_tv"],
        "steps_template": [
            {"action": "voice", "utterance": "{name} 틀어줘"},
            {"action": "capture", "duration": 2},
        ],
        "expected_template": "{name} 채널 표시",
        "expected_keywords_template": ["{name}"],
        "sla_ms": 5000,
        "change_signals": ["channel-list"],
        "axis": [
            {"slug": "kbs1", "name": "KBS1", "priority": "P1"},
            {"slug": "mbc", "name": "MBC", "priority": "P2"},
        ],
    }


def test_expand_family_count_and_fields():
    out = expand_family(_family())
    assert len(out) == 2
    a, b = out
    assert a["id"] == "epg_zap_kbs1" and a["priority"] == "P1"
    assert a["steps"][0]["utterance"] == "KBS1 틀어줘"
    assert a["expected"] == "KBS1 채널 표시"
    assert a["expected_keywords"] == ["KBS1"]
    assert a["change_signals"] == ["channel-list"]
    assert b["id"] == "epg_zap_mbc" and b["priority"] == "P2"


def test_expand_family_repeat_int_preserved():
    fam = {
        "id_template": "tp_{speed}",
        "category": "TrickPlay",
        "priority": "P2",
        "preconditions": [],
        "steps_template": [{"action": "ir", "key": "FF", "repeat": "{taps}"},
                           {"action": "capture", "duration": 2}],
        "expected_template": "{speed}",
        "sla_ms": 1000,
        "axis": [{"speed": "8x", "taps": 3}],
    }
    sc = expand_family(fam)[0]
    assert sc["steps"][0]["repeat"] == 3 and isinstance(sc["steps"][0]["repeat"], int)


def test_expand_all_dup_id_raises():
    spec = {"families": [_family(), _family()]}  # 같은 family 2번 → 같은 id 재생성
    with pytest.raises(ValueError, match="중복 생성 id"):
        expand_all(spec)


def test_check_collisions():
    gen = [{"id": "a"}, {"id": "b"}]
    assert check_collisions(gen, {"b", "c"}) == ["b"]


# ──────────────── 실제 param_spec.json ────────────────

def test_real_spec_generates_164():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    generated = expand_all(spec)
    assert len(generated) == 164


def test_real_spec_ids_unique():
    """생성된 164개 id는 내부적으로 모두 유일 (merge 후에도 안정)."""
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    ids = [s["id"] for s in expand_all(spec)]
    assert len(ids) == len(set(ids)) == 164


def test_real_spec_subset_of_merged_catalog():
    """merge 완료 후: 생성 id 전부가 카탈로그에 존재해야 (병합 성공 불변식)."""
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    generated_ids = {s["id"] for s in expand_all(spec)}
    catalog_ids = {s["id"] for s in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))}
    missing = generated_ids - catalog_ids
    assert not missing, f"카탈로그에 미반영된 생성 id: {sorted(missing)[:10]}"


def test_real_spec_all_scenarios_schema_valid_after_infer():
    """생성 시나리오가 infer_defaults 후 pydantic v2 schema 통과해야 머지 가능."""
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    for sc in expand_all(spec):
        Scenario(**infer_defaults(sc))   # raise 안 하면 통과


def test_real_spec_every_scenario_has_capture():
    """capture step 없으면 _run_scenario가 검증 불가 → 모든 시나리오에 capture 필수."""
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    for sc in expand_all(spec):
        actions = [s["action"] for s in sc["steps"]]
        assert "capture" in actions, f"{sc['id']}: capture step 없음"
