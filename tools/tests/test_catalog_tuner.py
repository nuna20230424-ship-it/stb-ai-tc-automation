"""catalog_tuner — lint / overrides + 실 카탈로그 클린 상태 검증."""
from __future__ import annotations

import json
from pathlib import Path

from tools.catalog_tuner.lint import Issue, lint_catalog, lint_scenario, summarize
from tools.catalog_tuner.overrides import apply_overrides
from tools.catalog_tuner.vocab import (
    load_known_keys,
    load_known_preconditions,
    load_known_states,
)

CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"
)

KNOWN_KEYS = {"OK", "CH_0", "CH_1", "MENU", "SEARCH", "RIGHT", "PLAY", "FF"}
KNOWN_STATES = {"home_screen", "live_tv", "epg_open"}
KNOWN_PRE = {"home_screen", "live_tv", "epg_open", "hdcp_unsupported_display"}


def _sc(sid="s1", steps=None, preconditions=None):
    return {
        "id": sid,
        "category": "EPG",
        "priority": "P2",
        "preconditions": preconditions or [],
        "steps": steps or [{"action": "ir", "key": "OK"}, {"action": "capture", "duration": 2}],
        "expected": "x",
        "sla_ms": 2000,
    }


def _lint(s):
    return lint_scenario(s, known_keys=KNOWN_KEYS, known_states=KNOWN_STATES,
                         known_preconditions=KNOWN_PRE)


# ──────────────── lint ────────────────

def test_lint_clean_scenario():
    assert _lint(_sc()) == []


def test_lint_unknown_key_with_suggestion():
    issues = _lint(_sc(steps=[{"action": "ir", "key": "SETTINGS"},
                              {"action": "capture", "duration": 2}]))
    assert len(issues) == 1
    assert issues[0].kind == "unknown_key" and issues[0].detail == "SETTINGS"


def test_lint_bare_digit_key():
    issues = _lint(_sc(steps=[{"action": "ir", "key": "1"},
                              {"action": "capture", "duration": 2}]))
    assert issues[0].kind == "unknown_key" and issues[0].detail == "1"
    # 맨 숫자는 difflib 근사가 안 잡힐 수 있음(제안 빈 문자열 허용) → SME가 overrides로 교정
    assert issues[0].suggestion == "" or issues[0].suggestion in KNOWN_KEYS


def test_lint_freetext_navigate():
    issues = _lint(_sc(steps=[{"action": "navigate", "path": "Netflix → 재생"},
                              {"action": "capture", "duration": 2}]))
    assert any(i.kind == "freetext_navigate" for i in issues)


def test_lint_known_navigate_ok():
    issues = _lint(_sc(steps=[{"action": "navigate", "path": "epg_open"},
                              {"action": "capture", "duration": 2}]))
    assert not any(i.kind == "freetext_navigate" for i in issues)


def test_lint_unknown_precondition():
    issues = _lint(_sc(preconditions=["mars_base"]))
    assert any(i.kind == "unknown_precondition" for i in issues)


def test_lint_empty_voice():
    issues = _lint(_sc(steps=[{"action": "voice", "utterance": "  "},
                              {"action": "capture", "duration": 2}]))
    assert any(i.kind == "empty_voice" for i in issues)


def test_lint_no_capture():
    issues = _lint(_sc(steps=[{"action": "ir", "key": "OK"}]))
    assert any(i.kind == "no_capture" for i in issues)


def test_summarize():
    issues = [Issue("a", "unknown_key", "x"), Issue("b", "unknown_key", "y"),
              Issue("c", "no_capture", "z")]
    assert summarize(issues) == {"unknown_key": 2, "no_capture": 1}


# ──────────────── overrides ────────────────

def test_apply_key_remap():
    cat = [_sc("p", steps=[{"action": "ir", "key": "1"}, {"action": "ir", "key": "0"},
                           {"action": "capture", "duration": 2}])]
    patched, log = apply_overrides(cat, {"key_remap": {"1": "CH_1", "0": "CH_0"}})
    keys = [st["key"] for st in patched[0]["steps"] if st["action"] == "ir"]
    assert keys == ["CH_1", "CH_0"]
    assert len(log.key_remaps) == 2
    assert cat[0]["steps"][0]["key"] == "1"  # 원본 불변


def test_apply_scenario_patch():
    cat = [_sc("drm", steps=[{"action": "navigate", "path": "x"}, {"action": "capture", "duration": 2}])]
    patch = {"scenario_patches": {"drm": {"steps": [{"action": "voice", "utterance": "재생"},
                                                     {"action": "capture", "duration": 3}],
                                          "sla_ms": 9000}}}
    patched, log = apply_overrides(cat, patch)
    assert patched[0]["sla_ms"] == 9000
    assert patched[0]["steps"][0]["action"] == "voice"
    assert "drm" in log.patched_scenarios


def test_apply_missing_patch_target_recorded():
    cat = [_sc("a")]
    _, log = apply_overrides(cat, {"scenario_patches": {"ghost": {"sla_ms": 1}}})
    assert log.missing_patch_targets == ["ghost"]


# ──────────────── 실 카탈로그: 튜닝 후 lint clean ────────────────

def test_real_catalog_lint_clean():
    """1차 튜닝 적용 후 실 카탈로그는 lint 이슈 0이어야 (회귀 안전망).

    예외: 업데이트 53에서 KAON 사내 엑셀 480건을 dry-run import 한 후 steps[]가
    빈 채로 카탈로그에 들어있음 (LLM 활성화 후 채워질 예정). 이 경우 `no_capture`
    이슈만 발생하므로 kaon_* prefix + no_capture 이슈는 일시 허용.
    """
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    issues = lint_catalog(
        catalog,
        known_keys=load_known_keys(),
        known_states=load_known_states(),
        known_preconditions=load_known_preconditions(),
    )

    # KAON dry-run import 항목 — Steps 후속 작업 대기 중
    others = [
        i for i in issues
        if not (i.scenario_id.startswith("kaon_") and i.kind == "no_capture")
    ]
    assert others == [], f"lint 이슈 재발생: {[i.to_dict() for i in others][:5]}"
