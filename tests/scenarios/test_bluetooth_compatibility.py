"""BT 호환성 시나리오 — 각 디바이스의 compat_checks를 순회 실행.

PoC는 캡처 + Detection 기반 표시 검증만 수행. Sprint 2부터 실제 입력·오디오 스트림 검증 확장.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pytest
from influxdb_client import Point, WritePrecision

from utils import extract_middle_frame

CATALOG_PATH = Path(__file__).resolve().parents[2] / "infrastructure" / "notebook-gateway" / "data" / "bt-device-catalog.json"
BT_DEVICES = json.loads(CATALOG_PATH.read_text())

# (device, check) 매트릭스 생성
MATRIX: list[tuple[dict, str]] = []
for d in BT_DEVICES:
    if d["priority"] in ("P1", "P2"):
        for chk in d["compat_checks"]:
            MATRIX.append((d, chk))


def _id(device_check: tuple[dict, str]) -> str:
    d, chk = device_check
    return f"{d['id']}-{chk}"


@pytest.mark.e2e
@pytest.mark.bluetooth
@pytest.mark.slow
@pytest.mark.parametrize("device_check", MATRIX, ids=_id)
def test_bt_compatibility(device_check, gateway, backend, metrics, env):
    device, check = device_check
    scenario = f"bt_compat_{device['id']}_{check}"

    # 페어링 상태 가정 — test_bluetooth_pairing이 선행 통과되어야 함
    # 실제로는 pytest-dependency 또는 fixture로 의존성 명시 가능

    if check == "pair":
        # 페어링 상태 화면 확인
        gateway.ir.send(env["ir_codeset"], "BT_SETTINGS")
        time.sleep(2)
    elif check == "key_input":
        # HID 입력: 디바이스에서 키 1회 송신 (PoC: 수동 안내)
        print(f"\n[ACTION] {device['name']}의 OK 키를 한 번 누르세요.")
        time.sleep(3)
    elif check == "voice_capture":
        gateway.voice.speak("음악 채널 틀어줘")  # 디바이스 마이크 경유 흐름
        time.sleep(1)
    elif check == "audio_stream":
        # A2DP: STB → 헤드폰/스피커. 비디오 재생 후 화면+소리 확인
        gateway.ir.send(env["ir_codeset"], "PLAY")
        time.sleep(3)
    elif check == "avrcp_control":
        # AVRCP: 디바이스에서 미디어 제어 (Play/Pause)
        print(f"\n[ACTION] {device['name']} Play/Pause 버튼을 누르세요.")
        time.sleep(3)
    elif check == "battery_status":
        gateway.ir.send(env["ir_codeset"], "DEVICE_INFO")
        time.sleep(2)
    else:
        pytest.skip(f"unknown compat check: {check}")

    # 검증: 화면 캡처 + Detection
    cap = gateway.capture.capture("dut", duration_sec=2, label=scenario)
    frame = extract_middle_frame(Path(cap["path"]))
    verdict = backend.detection.check_screen(scenario=scenario, image_path=frame,
                                              firmware=env["firmware"])

    # 메트릭 기록
    point = (Point("bluetooth_compatibility")
             .tag("device_id", device["id"])
             .tag("check", check)
             .tag("vendor", device["vendor"])
             .tag("verdict", verdict["verdict"])
             .field("function_pass", 1 if verdict["verdict"] == "normal" else 0)
             .field("score", float(verdict["best_score"]))
             .time(datetime.utcnow(), WritePrecision.NS))
    metrics.write_api.write(bucket=metrics.bucket, org=metrics.org, record=point)

    if verdict["verdict"] == "anomaly":
        backend.report.create_incident(
            scenario=scenario,
            severity=env["jira_severity"],
            summary=f"[BT compat] {device['name']} - {check} 실패",
            description=(
                f"디바이스: {device['name']} ({device['vendor']})\n"
                f"점검 항목: {check}\n"
                f"score: {verdict['best_score']:.3f}\n"
            ),
            evidence_url=str(frame),
        )

    assert verdict["verdict"] == "normal", verdict
