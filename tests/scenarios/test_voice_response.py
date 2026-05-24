"""음성 발화 응답 시나리오 — voice catalog의 각 발화에 대해
TTS 재생 → STB 응답 화면 캡처 → Detection 비교 → 응답 지연 측정.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from utils import extract_middle_frame

CATALOG_PATH = Path(__file__).resolve().parents[2] / "infrastructure" / "notebook-gateway" / "data" / "voice-command-catalog.json"
VOICE_COMMANDS = json.loads(CATALOG_PATH.read_text())
P1_COMMANDS = [c for c in VOICE_COMMANDS if c["priority"] == "P1"]


@pytest.mark.e2e
@pytest.mark.voice
@pytest.mark.parametrize("cmd", P1_COMMANDS, ids=[c["id"] for c in P1_COMMANDS])
def test_voice_response(cmd, gateway, backend, metrics, env):
    scenario = cmd["id"]

    # 1) DUT 부팅 보장 (idempotent)
    gateway.power.set("dut", on=True)

    # 2) TTS 재생 — 발화 종료 시각이 응답 지연 기준
    spoken = gateway.voice.speak(cmd["utterance"])
    t_end_speak = spoken["end_epoch"]

    # 3) 즉시 캡처 시작 (3초간)
    capture = gateway.capture.capture("dut", duration_sec=3, label=scenario)
    t_capture_done = time.time()
    response_ms = int((t_capture_done - t_end_speak) * 1000)

    # 4) 중간 프레임 추출
    frame = extract_middle_frame(Path(capture["path"]))

    # 5) Detection 비교
    verdict = backend.detection.check_screen(
        scenario=scenario,
        image_path=frame,
        firmware=env["firmware"],
    )

    # 6) 메트릭 기록
    metrics.detection_result(scenario, verdict["best_score"], verdict["verdict"])
    # voice_command measurement (response_ms, intent_match)
    from influxdb_client import Point, WritePrecision
    from datetime import datetime
    point = (Point("voice_command")
             .tag("scenario", scenario)
             .tag("intent", cmd["intent"])
             .tag("verdict", verdict["verdict"])
             .field("response_ms", response_ms)
             .field("intent_match", 1 if verdict["verdict"] == "normal" else 0)
             .time(datetime.utcnow(), WritePrecision.NS))
    metrics.write_api.write(bucket=metrics.bucket, org=metrics.org, record=point)

    # 7) 이상 시 JIRA 등록
    if verdict["verdict"] == "anomaly":
        incident = backend.report.create_incident(
            scenario=scenario,
            severity=env["jira_severity"],
            summary=f"[Voice] '{cmd['utterance']}' 의도 매칭 실패 (score={verdict['best_score']:.3f})",
            description=(
                f"발화: {cmd['utterance']}\n"
                f"기대 화면: {cmd['expected_screen']}\n"
                f"응답 지연: {response_ms} ms (SLA {cmd['sla_response_ms']})\n"
                f"Vision 묘사: {verdict.get('description', 'N/A')}\n"
            ),
            evidence_url=str(frame),
        )
        pytest.fail(f"voice intent mismatch — JIRA={incident.get('jira_url')}")

    # 8) Assertions
    assert verdict["verdict"] == "normal", verdict
    assert response_ms < cmd["sla_response_ms"], (
        f"응답 지연 SLA 초과: {response_ms}ms > {cmd['sla_response_ms']}ms"
    )


@pytest.mark.e2e
@pytest.mark.voice
def test_voice_repeat_consistency(gateway, backend, metrics, env):
    """동일 발화 5회 → 모두 동일 verdict, score 변동 < 0.10."""
    cmd = P1_COMMANDS[0]  # 첫 P1 발화
    scores: list[float] = []
    verdicts: list[str] = []

    for i in range(5):
        gateway.voice.speak(cmd["utterance"])
        time.sleep(1)
        cap = gateway.capture.capture("dut", duration_sec=2, label=f"{cmd['id']}-iter{i}")
        frame = extract_middle_frame(Path(cap["path"]))
        v = backend.detection.check_screen(scenario=cmd["id"], image_path=frame)
        scores.append(v["best_score"])
        verdicts.append(v["verdict"])

    drift = max(scores) - min(scores)
    assert drift < 0.10, f"voice drift 발생: scores={scores}"
    assert all(x == "normal" for x in verdicts), f"voice 일관성 실패: {verdicts}"
