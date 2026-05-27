"""tc_selector — component_map / selector / flake 단위 테스트."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tools.tc_selector.component_map import (
    components_to_signals,
    paths_to_signals,
    unmatched_paths,
)
from tools.tc_selector.flake import (
    flake_score,
    pass_rate,
    quarantine_list,
    should_quarantine,
    update_flake_history,
)
from tools.tc_selector.selector import (
    estimate_runtime_sec,
    explain,
    firmware_in_range,
    is_impacted,
    select,
)

COMPONENT_MAP = {
    "src/epg/**": ["epg-engine", "channel-list"],
    "src/voice/**": ["voice-asr"],
    "src/drm/**": ["drm-cdm", "hdcp"],
}


def _sc(sid, signals, risk=4, runtime=None, fw_min=None, fw_max=None, flake=None) -> dict:
    return {
        "id": sid,
        "category": "EPG",
        "priority": "P1" if risk >= 4 else "P2",
        "steps": [{"action": "ir", "key": "EPG"}, {"action": "capture", "duration": 2}],
        "expected": "x",
        "sla_ms": 2000,
        "risk_weight": risk,
        "change_signals": signals,
        "avg_runtime_sec": runtime,
        "firmware_min": fw_min,
        "firmware_max": fw_max,
        "flake_history": flake or {"runs": 0, "passes": 0, "last_failures": []},
    }


# ──────────────── component_map ────────────────

def test_paths_to_signals_glob():
    sigs = paths_to_signals(["src/voice/asr.c", "src/epg/grid.c"], COMPONENT_MAP)
    assert sigs == {"voice-asr", "epg-engine", "channel-list"}


def test_paths_to_signals_unmatched_ignored():
    sigs = paths_to_signals(["README.md", "docs/x.md"], COMPONENT_MAP)
    assert sigs == set()


def test_unmatched_paths():
    un = unmatched_paths(["src/voice/x.c", "README.md"], COMPONENT_MAP)
    assert un == ["README.md"]


def test_components_to_signals_passthrough():
    assert components_to_signals(["voice-asr", "EPG-Engine"]) == {"voice-asr", "epg-engine"}


def test_components_to_signals_alias():
    out = components_to_signals(["av"], aliases={"av": ["video-pipeline", "media-stack"]})
    assert out == {"video-pipeline", "media-stack"}


# ──────────────── selector: runtime/firmware/impact ────────────────

def test_estimate_runtime_uses_avg_when_present():
    assert estimate_runtime_sec(_sc("a", ["x"], runtime=42.0)) == 42.0


def test_estimate_runtime_falls_back_to_steps():
    sc = _sc("a", ["x"], runtime=None)
    # base 4 + ir 1.5 + capture 2 = 7.5
    assert estimate_runtime_sec(sc) == pytest.approx(7.5)


def test_firmware_in_range():
    sc = _sc("a", ["x"], fw_min="v1.2.0", fw_max="v2.0.0")
    assert firmware_in_range(sc, "v1.5.0")
    assert not firmware_in_range(sc, "v1.1.0")
    assert not firmware_in_range(sc, "v2.1.0")
    assert firmware_in_range(sc, None)  # firmware 미지정 → 항상 통과


def test_is_impacted_full_when_none():
    assert is_impacted(_sc("a", ["epg-engine"]), None) is True


def test_is_impacted_intersection():
    sc = _sc("a", ["epg-engine", "tuner"])
    assert is_impacted(sc, {"voice-asr"}) is False
    assert is_impacted(sc, {"tuner"}) is True


# ──────────────── selector: select ────────────────

def test_select_only_impacted():
    catalog = [
        _sc("epg1", ["epg-engine"]),
        _sc("voice1", ["voice-asr"]),
        _sc("drm1", ["drm-cdm"]),
    ]
    r = select(catalog, {"voice-asr"}, budget_sec=10000)
    ids = {t.id for t in r.selected}
    assert ids == {"voice1"}
    assert set(r.skipped_not_impacted) == {"epg1", "drm1"}


def test_select_full_regression():
    catalog = [_sc("a", ["x"]), _sc("b", ["y"])]
    r = select(catalog, None, budget_sec=10000)
    assert len(r.selected) == 2
    assert all(t.reason == "full" for t in r.selected)


def test_select_budget_greedy_defers_low_risk():
    # 높은 risk 먼저 채우고 예산 초과분은 deferred
    catalog = [
        _sc("hi", ["x"], risk=5, runtime=100),
        _sc("lo", ["x"], risk=2, runtime=100),
    ]
    r = select(catalog, {"x"}, budget_sec=120)  # 하나만 들어감
    assert [t.id for t in r.selected] == ["hi"]
    assert [t.id for t in r.deferred] == ["lo"]


def test_select_savings_pct():
    catalog = [_sc("a", ["x"], runtime=100), _sc("b", ["y"], runtime=300)]
    r = select(catalog, {"x"}, budget_sec=10000)
    # eligible 400, selected 100 → 75% 절약
    assert r.selected_sec == 100
    assert r.eligible_sec == 400
    assert r.savings_pct == 75.0


def test_select_smoke_always_included():
    catalog = [_sc("smoke", ["unrelated"], risk=5)]
    r = select(catalog, {"voice-asr"}, budget_sec=10000, smoke_risk_min=5)
    assert [t.id for t in r.selected] == ["smoke"]
    assert r.selected[0].reason == "smoke"


def test_select_firmware_skip():
    catalog = [_sc("old", ["x"], fw_max="v1.0.0")]
    r = select(catalog, {"x"}, budget_sec=10000, firmware="v2.0.0")
    assert r.skipped_firmware == ["old"]
    assert not r.selected


def test_select_excludes_quarantined():
    flaky = {"runs": 20, "passes": 10, "last_failures": []}  # 50% fail
    catalog = [_sc("flaky", ["x"], flake=flaky), _sc("stable", ["x"])]
    r = select(catalog, {"x"}, budget_sec=10000)
    assert r.quarantined == ["flaky"]
    assert [t.id for t in r.selected] == ["stable"]


def test_pytest_k_expression():
    catalog = [_sc("a", ["x"]), _sc("b", ["x"])]
    r = select(catalog, {"x"}, budget_sec=10000)
    assert r.pytest_k() == "a or b"


# ──────────────── flake ────────────────

def test_pass_rate_no_runs():
    assert pass_rate({"runs": 0, "passes": 0}) == 1.0


def test_flake_score():
    assert flake_score({"runs": 10, "passes": 7}) == pytest.approx(0.3)


def test_should_quarantine_needs_min_runs():
    assert not should_quarantine({"runs": 3, "passes": 0}, min_runs=10)
    assert should_quarantine({"runs": 10, "passes": 5}, min_runs=10, max_fail_rate=0.3)


def test_quarantine_list():
    catalog = [
        _sc("bad", ["x"], flake={"runs": 20, "passes": 10, "last_failures": []}),
        _sc("good", ["x"], flake={"runs": 20, "passes": 20, "last_failures": []}),
    ]
    q = quarantine_list(catalog)
    assert [item["id"] for item in q] == ["bad"]


def test_update_flake_history_pass():
    fh = {"runs": 5, "passes": 4, "last_failures": []}
    new = update_flake_history(fh, passed=True)
    assert new["runs"] == 6 and new["passes"] == 5
    assert fh["runs"] == 5  # 원본 불변


def test_update_flake_history_fail_records_ts():
    now = datetime(2026, 5, 27, tzinfo=timezone.utc)
    new = update_flake_history({"runs": 1, "passes": 1, "last_failures": []}, passed=False, now=now)
    assert new["passes"] == 1 and new["runs"] == 2
    assert new["last_failures"] == ["2026-05-27T00:00:00+00:00"]


def test_update_flake_history_caps_failures():
    fh = {"runs": 100, "passes": 0, "last_failures": [f"ts{i}" for i in range(10)]}
    new = update_flake_history(fh, passed=False, keep_failures=10)
    assert len(new["last_failures"]) == 10


def test_explain_structure():
    sc = _sc("a", ["epg-engine", "tuner"])
    info = explain(sc, {"tuner"})
    assert info["impacted"] is True
    assert info["matched_signals"] == ["tuner"]
