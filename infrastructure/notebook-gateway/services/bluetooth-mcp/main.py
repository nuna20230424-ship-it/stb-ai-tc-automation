"""Bluetooth MCP — STB가 BT 디바이스를 페어링·사용 가능한지 검증하는 보조 도구.

핵심 역할:
  - 노트북 BT 스택으로 주변 BT 광고 스캔 (디바이스가 페어링 모드인지 확인)
  - 디바이스 카탈로그 JSON에서 우선순위 디바이스 조회
  - 페어링 모드 진입 안내 (PoC: 운영자 트리거, Sprint 2: GPIO 푸셔)

설계: 페어링 자체는 STB가 BT 호스트로 수행하므로, 본 MCP는 광고/디바이스 카탈로그 검증과
페어링 모드 트리거 보조 역할만 담당.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

from bleak import BleakScanner
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-bluetooth-mcp")

CATALOG_PATH = Path(os.getenv("BT_CATALOG_PATH", "/data/bt-device-catalog.json"))


class ScanRequest(BaseModel):
    duration_sec: int = 10
    filter_name: str | None = None    # 부분 일치
    filter_mac: str | None = None     # 정확 일치 (대소문자 무관)


def _load_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    return json.loads(CATALOG_PATH.read_text())


@app.get("/health")
def health():
    catalog = _load_catalog()
    return {
        "status": "ok",
        "service": "bluetooth-mcp",
        "catalog_devices": len(catalog),
        "catalog_path": str(CATALOG_PATH),
    }


@app.get("/catalog")
def catalog():
    return {"devices": _load_catalog()}


@app.post("/scan")
async def scan(req: ScanRequest):
    """주변 BT 광고를 듀레이션만큼 스캔하여 발견된 디바이스 반환."""
    discovered: dict[str, dict] = {}

    def callback(device, advertisement_data):
        key = device.address.upper()
        discovered[key] = {
            "mac": device.address,
            "name": device.name or "",
            "rssi": advertisement_data.rssi,
            "uuids": list(advertisement_data.service_uuids or []),
            "manufacturer": advertisement_data.manufacturer_data,
        }

    scanner = BleakScanner(detection_callback=callback)
    await scanner.start()
    await asyncio.sleep(req.duration_sec)
    await scanner.stop()

    devices = list(discovered.values())
    if req.filter_name:
        devices = [d for d in devices if req.filter_name.lower() in d["name"].lower()]
    if req.filter_mac:
        devices = [d for d in devices if d["mac"].lower() == req.filter_mac.lower()]
    return {"discovered": devices, "count": len(devices)}


@app.get("/verify_advertising/{mac}")
async def verify_advertising(mac: str, duration_sec: int = 5):
    """특정 MAC이 광고 중인지 빠르게 확인 (페어링 모드 진입 검증용)."""
    result = await scan(ScanRequest(duration_sec=duration_sec, filter_mac=mac))
    return {"mac": mac, "advertising": result["count"] > 0, "details": result["discovered"]}


@app.post("/trigger_pairing/{device_id}")
def trigger_pairing(device_id: str):
    """디바이스 카탈로그에서 device_id 조회, PoC 단계에선 운영자에게 페어링 모드 진입 요청.

    Sprint 2: GPIO 푸셔 + 라즈베리파이 연동으로 자동 트리거.
    """
    catalog_list = _load_catalog()
    device = next((d for d in catalog_list if d.get("id") == device_id), None)
    if not device:
        raise HTTPException(404, f"device_id not in catalog: {device_id}")

    # PoC: 운영자 안내 메시지 반환 (실제 트리거는 수동)
    return {
        "device_id": device_id,
        "device": device,
        "action_required": "MANUAL",
        "instruction": device.get("pairing_instruction", "디바이스의 페어링 버튼을 길게 눌러 페어링 모드로 진입시키세요."),
        "expected_advertise_within_sec": device.get("expected_advertise_within_sec", 5),
    }


@app.get("/host_info")
def host_info():
    """노트북 BT 어댑터 정보 (디버깅용)."""
    try:
        # Linux: hciconfig, Mac: blueutil --info / system_profiler
        result = subprocess.run(
            ["hciconfig", "-a"], capture_output=True, text=True, timeout=5
        )
        return {"output": result.stdout, "stderr": result.stderr}
    except FileNotFoundError:
        return {"warning": "hciconfig not available (macOS uses different tools)"}


@app.get("/tools")
def tools():
    return {
        "tools": [
            {"name": "scan", "description": "주변 BT 광고 스캔 (BLE)"},
            {"name": "verify_advertising", "description": "특정 MAC이 광고 중인지 확인"},
            {"name": "trigger_pairing", "description": "디바이스 페어링 모드 진입 요청 (PoC: 수동)"},
            {"name": "catalog", "description": "BT 디바이스 카탈로그 조회"},
        ]
    }
