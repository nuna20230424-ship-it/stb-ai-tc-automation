"""카탈로그 기반 시나리오 자동 실행 — EPG / OTT / DRM / TrickPlay 통합.

scenarios-catalog.json의 각 시나리오를 steps 배열대로 순차 실행 →
캡처 → embedding → detection → InfluxDB 기록 → 이상 시 JIRA 등록.

마커: -m epg / ott / drm / trickplay / catalog 로 필터링.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pytest
from influxdb_client import Point, WritePrecision

from preconditions.fixtures import apply_preconditions
from utils import extract_middle_frame

CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"
)
ALL_SCENARIOS = json.loads(CATALOG_PATH.read_text())


def _filter(category: str, priority: str | None = None) -> list[dict]:
    return [
        s for s in ALL_SCENARIOS
        if s["category"].lower() == category.lower()
        and (priority is None or s["priority"] == priority)
    ]


def _ids(scenarios: list[dict]) -> list[str]:
    return [s["id"] for s in scenarios]


def _exec_step(step: dict, gateway, env) -> Path | None:
    """단일 step 실행. action별 분기. 마지막 capture는 frame 경로 반환."""
    action = step["action"]
    repeat = step.get("repeat", 1)

    if action == "ir":
        for _ in range(repeat):
            gateway.ir.send(env["ir_codeset"], step["key"])
            time.sleep(0.15)
        return None

    if action == "voice":
        gateway.voice.speak(step["utterance"])
        return None

    if action == "wait":
        time.sleep(step["sec"])
        return None

    if action == "capture":
        label = step.get("label", "step")
        cap = gateway.capture.capture("dut", duration_sec=step.get("duration", 2), label=label)
        return extract_middle_frame(Path(cap["path"]))

    if action == "navigate":
        # PoC: 자연어 navigate는 운영자 안내 또는 사전 정의 매크로 (Sprint 2 확장)
        # 여기선 단순 wait + capture로 대체
        time.sleep(2)
        return None

    raise ValueError(f"unknown action: {action}")


def _run_scenario(scenario: dict, gateway, backend, metrics, env, request):
    """카탈로그 시나리오 1건 실행 → preconditions 자동 도달 → 마지막 capture 프레임 검증."""
    scenario_id = scenario["id"]
    last_frame: Path | None = None

    # Sprint 2: preconditions 자동 적용 (fixture 동적 dispatch)
    apply_preconditions(request, scenario.get("preconditions", []))

    t0 = time.monotonic()
    for step in scenario["steps"]:
        result = _exec_step(step, gateway, env)
        if isinstance(result, Path):
            last_frame = result

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    if last_frame is None:
        pytest.fail(f"{scenario_id}: capture step이 없어 검증 불가")

    verdict = backend.detection.check_screen(
        scenario=scenario_id,
        image_path=last_frame,
        firmware=env["firmware"],
    )
    metrics.detection_result(scenario_id, verdict["best_score"], verdict["verdict"])

    # catalog_runs measurement 기록
    point = (Point("catalog_runs")
             .tag("scenario", scenario_id)
             .tag("category", scenario["category"])
             .tag("priority", scenario["priority"])
             .tag("verdict", verdict["verdict"])
             .field("elapsed_ms", elapsed_ms)
             .field("score", float(verdict["best_score"]))
             .time(datetime.utcnow(), WritePrecision.NS))
    metrics.write_api.write(bucket=metrics.bucket, org=metrics.org, record=point)

    # 이상 시 JIRA 등록
    if verdict["verdict"] == "anomaly":
        backend.report.create_incident(
            scenario=scenario_id,
            severity=env["jira_severity"],
            summary=f"[{scenario['category']}] {scenario_id} 비정상 (score={verdict['best_score']:.3f})",
            description=(
                f"기대 화면: {scenario['expected']}\n"
                f"실행 시간: {elapsed_ms}ms (SLA {scenario['sla_ms']}ms)\n"
                f"Vision 묘사: {verdict.get('description', 'N/A')}\n"
            ),
            evidence_url=str(last_frame),
        )
        pytest.fail(f"{scenario_id} anomaly: {verdict}")

    assert verdict["verdict"] == "normal", verdict
    assert elapsed_ms < scenario["sla_ms"] * 2, f"SLA 2배 초과: {elapsed_ms}ms"


# ────────────────────────────────────────────────────────────
# 카테고리별 parametrize
# ────────────────────────────────────────────────────────────

EPG_P1 = _filter("EPG", "P1")
OTT_P1 = _filter("OTT", "P1")
DRM_P1 = _filter("DRM", "P1")
TRICKPLAY_P1 = _filter("TrickPlay", "P1")
# Sprint 2 카탈로그 확장
SEARCH_P1 = _filter("Search", "P1")
RECORDING_P1 = _filter("Recording", "P1")
PARENTAL_P1 = _filter("Parental", "P1")
SETTINGS_P1 = _filter("Settings", "P1")


@pytest.mark.e2e
@pytest.mark.catalog
@pytest.mark.epg
@pytest.mark.parametrize("scenario", EPG_P1, ids=_ids(EPG_P1))
def test_epg(scenario, gateway, backend, metrics, env, request):
    _run_scenario(scenario, gateway, backend, metrics, env, request)


@pytest.mark.e2e
@pytest.mark.catalog
@pytest.mark.ott
@pytest.mark.parametrize("scenario", OTT_P1, ids=_ids(OTT_P1))
def test_ott(scenario, gateway, backend, metrics, env, request):
    _run_scenario(scenario, gateway, backend, metrics, env, request)


@pytest.mark.e2e
@pytest.mark.catalog
@pytest.mark.drm
@pytest.mark.parametrize("scenario", DRM_P1, ids=_ids(DRM_P1))
def test_drm(scenario, gateway, backend, metrics, env, request):
    _run_scenario(scenario, gateway, backend, metrics, env, request)


@pytest.mark.e2e
@pytest.mark.catalog
@pytest.mark.trickplay
@pytest.mark.parametrize("scenario", TRICKPLAY_P1, ids=_ids(TRICKPLAY_P1))
def test_trickplay(scenario, gateway, backend, metrics, env, request):
    _run_scenario(scenario, gateway, backend, metrics, env, request)


@pytest.mark.e2e
@pytest.mark.catalog
@pytest.mark.search
@pytest.mark.parametrize("scenario", SEARCH_P1, ids=_ids(SEARCH_P1))
def test_search(scenario, gateway, backend, metrics, env, request):
    _run_scenario(scenario, gateway, backend, metrics, env, request)


@pytest.mark.e2e
@pytest.mark.catalog
@pytest.mark.recording
@pytest.mark.parametrize("scenario", RECORDING_P1, ids=_ids(RECORDING_P1))
def test_recording(scenario, gateway, backend, metrics, env, request):
    _run_scenario(scenario, gateway, backend, metrics, env, request)


@pytest.mark.e2e
@pytest.mark.catalog
@pytest.mark.parental
@pytest.mark.parametrize("scenario", PARENTAL_P1, ids=_ids(PARENTAL_P1))
def test_parental(scenario, gateway, backend, metrics, env, request):
    _run_scenario(scenario, gateway, backend, metrics, env, request)


@pytest.mark.e2e
@pytest.mark.catalog
@pytest.mark.settings
@pytest.mark.parametrize("scenario", SETTINGS_P1, ids=_ids(SETTINGS_P1))
def test_settings(scenario, gateway, backend, metrics, env, request):
    _run_scenario(scenario, gateway, backend, metrics, env, request)
