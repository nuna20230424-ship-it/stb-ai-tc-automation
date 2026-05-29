"""console_data — classifier + builder + CLI 단위 테스트."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.console_data.builder import (
    BuildContext,
    build_console_data,
    build_summary,
    load_runs_from_json,
    merge_scenario,
)
from tools.console_data.classifier import ClassifyContext, classify_unrun
from tools.console_data.cli import main as cli_main


# ──────────────────────────────────────────────────────────
# 시나리오 헬퍼
# ──────────────────────────────────────────────────────────


def _scn(
    sid: str = "epg_open_7day",
    *,
    category: str = "EPG",
    priority: str = "P1",
    preconditions: list[str] | None = None,
    tags: list[str] | None = None,
    baseline_vector_id: str | None = "vec_001",
    fw_min: str | None = None,
    fw_max: str | None = None,
    flake: dict | None = None,
    sla_ms: int = 2000,
) -> dict:
    return {
        "id": sid,
        "category": category,
        "priority": priority,
        "preconditions": preconditions or [],
        "tags": tags or [],
        "expected": "EPG 7-day grid visible",
        "sla_ms": sla_ms,
        "baseline_vector_id": baseline_vector_id,
        "firmware_min": fw_min,
        "firmware_max": fw_max,
        "flake_history": flake or {"runs": 0, "passes": 0, "last_failures": []},
        "risk_weight": 4,
        "change_signals": ["epg-engine"],
    }


# ──────────────────────────────────────────────────────────
# classifier — 8 우선순위 규칙
# ──────────────────────────────────────────────────────────


class TestClassifier:
    def test_manual_only_returns_na(self):
        s = _scn(tags=["manual_only"])
        r = classify_unrun(s, ClassifyContext())
        assert r["status"] == "na"
        assert "영구 제외" in r["reason"]

    def test_firmware_out_of_range_returns_na(self):
        s = _scn(fw_min="2.0.0", fw_max="3.0.0")
        r = classify_unrun(s, ClassifyContext(firmware="1.0.0"))
        assert r["status"] == "na"
        assert "펌웨어" in r["reason"]

    def test_flake_quarantine_returns_na(self):
        s = _scn(flake={"runs": 10, "passes": 2, "last_failures": [1, 1, 1, 1, 1]})
        r = classify_unrun(s, ClassifyContext())
        assert r["status"] == "na"
        assert "flake" in r["reason"]

    def test_missing_baseline_returns_nt(self):
        s = _scn(baseline_vector_id=None)
        r = classify_unrun(s, ClassifyContext())
        assert r["status"] == "nt"
        assert "베이스라인" in r["reason"]

    def test_missing_credentials_returns_nt(self):
        s = _scn(preconditions=["netflix_logged_in"])
        r = classify_unrun(s, ClassifyContext(available_credentials=set()))
        assert r["status"] == "nt"
        assert "netflix_credentials" in r["reason"]

    def test_credentials_satisfied_falls_through(self):
        s = _scn(preconditions=["netflix_logged_in"])
        r = classify_unrun(s, ClassifyContext(available_credentials={"netflix_credentials"}))
        # 다른 규칙 모두 통과 → 8. 기타
        assert r["status"] == "nt"
        assert "사유 미상" in r["reason"]

    def test_deferred_returns_nt(self):
        s = _scn(sid="epg_x")
        r = classify_unrun(s, ClassifyContext(deferred_ids={"epg_x"}))
        assert r["status"] == "nt"
        assert "deferred" in r["reason"]

    def test_mcp_unreachable_returns_nt(self):
        s = _scn()
        r = classify_unrun(s, ClassifyContext(mcp_unreachable=True))
        assert r["status"] == "nt"
        assert "MCP" in r["reason"]

    def test_fallback_unknown_reason(self):
        s = _scn()
        r = classify_unrun(s, ClassifyContext())
        assert r["status"] == "nt"
        assert "사유 미상" in r["reason"]

    def test_priority_manual_over_firmware(self):
        # manual_only가 가장 우선
        s = _scn(tags=["manual_only"], fw_min="999.0.0")
        r = classify_unrun(s, ClassifyContext(firmware="1.0.0"))
        assert r["status"] == "na"
        assert "영구 제외" in r["reason"]


# ──────────────────────────────────────────────────────────
# builder.merge_scenario — 실행 결과 머지
# ──────────────────────────────────────────────────────────


class TestMergeScenario:
    def test_pass_run_includes_match_meta(self):
        s = _scn()
        run = {
            "scenario_id": s["id"],
            "status": "pass",
            "elapsed_ms": 1500,
            "ran_at": "2026-05-29T03:00:00",
            "matched_keywords": ["EPG"],
            "confidence": 0.92,
            "tier": "embedding",
            "vision_describe": "EPG grid visible",
        }
        out = merge_scenario(s, run, ClassifyContext())
        assert out["status"] == "pass"
        assert out["matched_keywords"] == ["EPG"]
        assert out["confidence"] == 0.92
        assert out["evidence"]["capture_png"].endswith("frame_00.png")
        assert out["sla_exceeded"] is False or out["sla_exceeded"] == 0

    def test_fail_run_has_reason_fields(self):
        s = _scn()
        run = {
            "scenario_id": s["id"],
            "status": "fail",
            "elapsed_ms": 5000,
            "ran_at": "2026-05-29T03:00:00",
            "fail_reason": "타임아웃",
            "fail_detail": "EPG 응답 없음",
        }
        out = merge_scenario(s, run, ClassifyContext())
        assert out["status"] == "fail"
        assert out["fail_reason"] == "타임아웃"
        assert out["sla_exceeded"] is True

    def test_no_run_invokes_classifier(self):
        s = _scn(baseline_vector_id=None)
        out = merge_scenario(s, None, ClassifyContext())
        assert out["status"] == "nt"
        assert out["nt_reason"].startswith("베이스라인")
        assert out["evidence"] == {}


# ──────────────────────────────────────────────────────────
# build_summary + build_console_data
# ──────────────────────────────────────────────────────────


class TestBuildSummary:
    def test_counts_by_status_and_category(self):
        tcs = [
            {"status": "pass", "category": "EPG"},
            {"status": "pass", "category": "EPG"},
            {"status": "fail", "category": "EPG"},
            {"status": "nt", "category": "OTT"},
            {"status": "na", "category": "OTT"},
        ]
        s = build_summary(tcs)
        assert s["total"] == 5
        assert s["pass"] == 2
        assert s["fail"] == 1
        assert s["nt"] == 1
        assert s["na"] == 1
        assert s["by_category"][0]["name"] == "EPG"
        assert s["by_category"][0]["pass"] == 2


class TestBuildConsoleData:
    def test_full_payload_shape(self):
        catalog = [
            _scn("epg_open_7day"),
            _scn("ott_netflix_login", category="OTT", preconditions=["netflix_logged_in"]),
            _scn("settings_reset", category="Settings", tags=["manual_only"]),
        ]
        runs = {
            "epg_open_7day": {
                "scenario_id": "epg_open_7day",
                "status": "pass",
                "elapsed_ms": 1200,
                "ran_at": "2026-05-29T03:00:00",
            }
        }
        ctx = BuildContext(firmware="1.0.0")
        payload = build_console_data(catalog, runs, ctx)
        assert payload["firmware"] == "1.0.0"
        assert payload["source"] == "real"
        assert payload["summary"]["total"] == 3
        assert payload["summary"]["pass"] == 1
        assert payload["summary"]["nt"] == 1  # OTT (missing netflix cred)
        assert payload["summary"]["na"] == 1  # Settings (manual_only)
        statuses = {t["id"]: t["status"] for t in payload["tcs"]}
        assert statuses == {
            "epg_open_7day": "pass",
            "ott_netflix_login": "nt",
            "settings_reset": "na",
        }


# ──────────────────────────────────────────────────────────
# load_runs_from_json
# ──────────────────────────────────────────────────────────


class TestLoadRunsFromJson:
    def test_list_form(self, tmp_path):
        p = tmp_path / "runs.json"
        p.write_text(
            json.dumps(
                [
                    {"scenario_id": "a", "status": "pass"},
                    {"scenario_id": "b", "status": "fail"},
                    {"missing_sid": True},
                ]
            )
        )
        runs = load_runs_from_json(p)
        assert set(runs.keys()) == {"a", "b"}

    def test_dict_form(self, tmp_path):
        p = tmp_path / "runs.json"
        p.write_text(json.dumps({"a": {"scenario_id": "a", "status": "pass"}}))
        runs = load_runs_from_json(p)
        assert "a" in runs

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_runs_from_json(tmp_path / "missing.json") == {}


# ──────────────────────────────────────────────────────────
# CLI 엔드 투 엔드
# ──────────────────────────────────────────────────────────


class TestCli:
    def test_build_command_writes_payload(self, tmp_path):
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text(
            json.dumps(
                [
                    _scn("epg_a"),
                    _scn("ott_b", category="OTT", preconditions=["netflix_logged_in"]),
                ]
            )
        )
        runs_path = tmp_path / "runs.json"
        runs_path.write_text(
            json.dumps(
                [{"scenario_id": "epg_a", "status": "pass", "elapsed_ms": 1100, "ran_at": "2026-05-29T03:00:00"}]
            )
        )
        out_path = tmp_path / "out" / "console-data.json"

        rc = cli_main(
            [
                "build",
                "--catalog",
                str(catalog_path),
                "--output",
                str(out_path),
                "--firmware",
                "1.2.3",
                "--runs-json",
                str(runs_path),
                "--available-credentials",
                "",
            ]
        )
        assert rc == 0
        assert out_path.exists()
        payload = json.loads(out_path.read_text())
        assert payload["firmware"] == "1.2.3"
        assert payload["source"] == "json"
        assert payload["summary"]["pass"] == 1
        assert payload["summary"]["nt"] == 1
