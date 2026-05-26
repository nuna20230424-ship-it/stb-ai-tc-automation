"""merge.py가 baseline_vector_id 누락 시 시드 명령 힌트를 출력하는지 검증."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _scenario(sid: str, baseline_id: str | None = None) -> dict:
    return {
        "id": sid,
        "category": "EPG",
        "priority": "P1",
        "preconditions": [],
        "steps": [
            {"action": "ir", "key": "EPG"},
            {"action": "capture", "duration": 2},
        ],
        "expected": "EPG 표시",
        "sla_ms": 2000,
        "risk_weight": 4,
        "firmware_min": None,
        "firmware_max": None,
        "tags": ["category:epg", "mcp:ir", "mcp:capture"],
        "flake_history": {"runs": 0, "passes": 0, "last_failures": []},
        "owner": None,
        "jira_epic": None,
        "baseline_vector_id": baseline_id,
        "change_signals": [],
        "avg_runtime_sec": None,
        "expected_keywords": [],
    }


def _run_merge(catalog: Path, drafts: list[Path], dry_run: bool = True) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable, "-m", "tools.catalog.merge",
        "--catalog", str(catalog),
        "--drafts", *(str(d) for d in drafts),
    ]
    if dry_run:
        cmd.append("--dry-run")
    return subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )


def test_merge_prints_missing_baseline_hint(tmp_path: Path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps([_scenario("epg_one", baseline_id="seeded")],
                                   ensure_ascii=False, indent=2), encoding="utf-8")

    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps([_scenario("epg_two", baseline_id=None)],
                                 ensure_ascii=False, indent=2), encoding="utf-8")

    result = _run_merge(catalog, [draft])
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "baseline_vector_id 누락 1건" in out
    assert "epg_two" in out
    assert "seed_catalog" in out


def test_merge_omits_hint_when_all_seeded(tmp_path: Path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps([_scenario("epg_one", baseline_id="seeded-a")],
                                   ensure_ascii=False, indent=2), encoding="utf-8")

    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps([_scenario("epg_two", baseline_id="seeded-b")],
                                 ensure_ascii=False, indent=2), encoding="utf-8")

    result = _run_merge(catalog, [draft])
    assert result.returncode == 0, result.stderr
    assert "baseline_vector_id 누락" not in result.stdout
