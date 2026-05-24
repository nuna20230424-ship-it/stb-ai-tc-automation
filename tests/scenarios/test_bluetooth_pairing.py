"""BT 페어링 시나리오 — 디바이스 카탈로그 P1을 STB가 페어링할 수 있는지 검증.

PoC 단계: 페어링 모드 진입은 운영자 수동. bluetooth-mcp가 광고 감지로 진입 확인.
Sprint 2+: GPIO 푸셔로 자동 트리거.
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
P1_DEVICES = [d for d in BT_DEVICES if d["priority"] == "P1"]

PAIRING_SLA_SEC = 10


@pytest.mark.e2e
@pytest.mark.bluetooth
@pytest.mark.parametrize("device", P1_DEVICES, ids=[d["id"] for d in P1_DEVICES])
def test_bt_pairing(device, gateway, backend, metrics, env, request):
    """디바이스 페어링 모드 진입 → STB가 발견·페어링 가능한지 확인."""
    scenario = f"bt_pair_{device['id']}"

    # 1) 디바이스 페어링 모드 진입 안내
    trigger = gateway.bluetooth.trigger_pairing(device["id"])
    print(f"\n[ACTION REQUIRED] {trigger['instruction']}")

    # PoC: 수동 트리거 대기 (CI에선 -p 옵션으로 자동 트리거 트리거 가능)
    if request.config.getoption("--auto", default=False) is False:
        input(f"  → {device['name']} 페어링 버튼 누른 뒤 Enter 키...")

    # 2) 노트북 BT 스택으로 광고 감지 (디바이스가 정상 진입했는지)
    t_pair_start = time.time()
    adv = gateway.bluetooth.verify_advertising(device["mac"], duration_sec=8)
    pairing_advertise_sec = time.time() - t_pair_start

    pairing_time_ms = int(pairing_advertise_sec * 1000)

    if not adv["advertising"]:
        # 광고 감지 실패 — JIRA 등록
        backend.report.create_incident(
            scenario=scenario,
            severity=env["jira_severity"],
            summary=f"[BT] {device['name']} 페어링 광고 감지 실패",
            description=(
                f"디바이스: {device['name']} ({device['mac']})\n"
                f"트리거 지시: {trigger['instruction']}\n"
                f"광고 감지 SLA: {device['expected_advertise_within_sec']}초\n"
                f"실측: {pairing_advertise_sec:.1f}초\n"
            ),
        )
        pytest.fail(f"BT advertising not detected for {device['mac']}")

    # 3) STB BT 설정 화면으로 진입 (IR로 메뉴 호출)
    gateway.ir.send(env["ir_codeset"], "MENU")
    time.sleep(2)
    gateway.ir.send(env["ir_codeset"], "BT_SETTINGS")  # codeset에 정의 필요
    time.sleep(3)

    # 4) STB BT 스캔 화면 캡처 → 디바이스 명 표시 확인
    cap = gateway.capture.capture("dut", duration_sec=3, label=scenario)
    frame = extract_middle_frame(Path(cap["path"]))
    verdict = backend.detection.check_screen(scenario=scenario, image_path=frame,
                                              firmware=env["firmware"])
    metrics.detection_result(scenario, verdict["best_score"], verdict["verdict"])

    # 5) bluetooth_pairing measurement 기록
    point = (Point("bluetooth_pairing")
             .tag("device_id", device["id"])
             .tag("vendor", device["vendor"])
             .tag("verdict", verdict["verdict"])
             .field("pairing_time_ms", pairing_time_ms)
             .field("success", 1 if verdict["verdict"] == "normal" else 0)
             .time(datetime.utcnow(), WritePrecision.NS))
    metrics.write_api.write(bucket=metrics.bucket, org=metrics.org, record=point)

    # 6) Assertions
    assert pairing_advertise_sec < PAIRING_SLA_SEC, (
        f"광고 감지 지연 SLA 초과: {pairing_advertise_sec:.1f}s > {PAIRING_SLA_SEC}s"
    )
    assert verdict["verdict"] == "normal", verdict
