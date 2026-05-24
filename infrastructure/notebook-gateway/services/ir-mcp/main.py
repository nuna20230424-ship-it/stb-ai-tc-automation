"""IR MCP — IR 송신 + (옵션) 학습.

백엔드 어댑터:
  - itach   : Global Caché iTach IP2IR (TCP 4998 sendir)         [송신 only by default]
  - broadlink: BroadLink RM4 Mini (python-broadlink, UDP)         [송신 + 학습]
  - itach-ilearner: iTach Flex/iLearner (TCP 4998 get_IRL)         [송신 + 학습]

IR_BACKEND 환경변수로 전환. 기본 itach.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from keyevents import ANDROID_TV_KEYEVENTS

app = FastAPI(title="stb-ir-mcp")

IR_BACKEND = os.getenv("IR_BACKEND", "itach").lower()
ITACH_HOST = os.getenv("ITACH_HOST", "10.0.10.20")
ITACH_PORT = int(os.getenv("ITACH_PORT", "4998"))
BROADLINK_HOST = os.getenv("BROADLINK_HOST", "192.168.1.50")
# ADB: 네트워크 디바이스(예: "192.168.1.100:5555") 또는 USB 시리얼(예: "ABCD1234")
ADB_TARGET = os.getenv("ADB_TARGET", "")
CODESET_DIR = Path(os.getenv("IR_CODESET_DIR", "/data/ir-codesets"))


class IRKeyRequest(BaseModel):
    codeset: str
    key: str


class IRLearnRequest(BaseModel):
    codeset: str
    key: str
    timeout_sec: int = 30


# ──────────────────────────────────────────────────────────────
# codeset I/O
# ──────────────────────────────────────────────────────────────

def _codeset_path(codeset: str) -> Path:
    return CODESET_DIR / f"{codeset}.json"


def _load_codeset(codeset: str) -> dict:
    p = _codeset_path(codeset)
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return data if isinstance(data, dict) else {}


def _save_codeset(codeset: str, data: dict) -> None:
    CODESET_DIR.mkdir(parents=True, exist_ok=True)
    p = _codeset_path(codeset)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ──────────────────────────────────────────────────────────────
# 백엔드 — 송신
# ──────────────────────────────────────────────────────────────

def _send_via_itach(payload: str) -> str:
    with socket.create_connection((ITACH_HOST, ITACH_PORT), timeout=3) as s:
        s.sendall((payload + "\r").encode())
        return s.recv(4096).decode().strip()


def _send_via_broadlink(payload: str) -> str:
    import broadlink  # type: ignore
    if not payload.startswith("broadlink:"):
        raise HTTPException(400, "BroadLink 백엔드는 'broadlink:' 접두사가 필요합니다")
    device = broadlink.hello(BROADLINK_HOST, timeout=5)
    device.auth()
    device.send_data(base64.b64decode(payload[len("broadlink:"):]))
    return "ok"


def _adb_cmd(args: list[str], timeout: int = 10) -> str:
    """adb -s <target> <args...> 실행 후 stdout 반환."""
    if not ADB_TARGET:
        raise HTTPException(500, "ADB_TARGET 환경변수가 설정되지 않음")
    cmd = ["adb", "-s", ADB_TARGET, *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, f"adb 시간 초과: {' '.join(cmd)}")
    except subprocess.CalledProcessError as e:
        raise HTTPException(502, f"adb 실패: {e.stderr.strip()[:200]}")
    return result.stdout.strip()


def _send_via_adb(payload: str) -> str:
    """payload가 'adb:keyevent:<NUM>' 또는 정수면 keyevent로 송신."""
    if payload.startswith("adb:keyevent:"):
        keyevent = payload[len("adb:keyevent:"):]
    elif payload.isdigit():
        keyevent = payload
    else:
        raise HTTPException(400, "ADB 백엔드는 'adb:keyevent:<NUM>' 형식이 필요합니다")
    return _adb_cmd(["shell", "input", "keyevent", keyevent])


def _send(payload: str) -> str:
    if IR_BACKEND in ("itach", "itach-ilearner"):
        return _send_via_itach(payload)
    if IR_BACKEND in ("broadlink", "rm4", "rm4-mini"):
        return _send_via_broadlink(payload)
    if IR_BACKEND in ("adb", "android-tv", "androidtv"):
        return _send_via_adb(payload)
    raise HTTPException(500, f"unsupported IR_BACKEND: {IR_BACKEND}")


# ──────────────────────────────────────────────────────────────
# 백엔드 — 학습
# ──────────────────────────────────────────────────────────────

def _learn_via_broadlink(timeout_sec: int) -> str:
    import broadlink  # type: ignore
    device = broadlink.hello(BROADLINK_HOST, timeout=5)
    device.auth()
    device.enter_learning()
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            data = device.check_data()
            if data:
                return "broadlink:" + base64.b64encode(data).decode()
        except Exception:
            pass
        time.sleep(0.3)
    raise HTTPException(408, "학습 시간 초과 (BroadLink)")


def _learn_via_itach(timeout_sec: int) -> str:
    s = socket.create_connection((ITACH_HOST, ITACH_PORT), timeout=10)
    try:
        s.sendall(b"get_IRL\r")
        ack = s.recv(4096).decode().strip()
        if "IR Learner Enabled" not in ack:
            raise HTTPException(500, f"iTach 학습모드 진입 실패: {ack}")
        s.settimeout(timeout_sec)
        data = s.recv(8192).decode().strip()
        if not data.startswith("sendir"):
            raise HTTPException(500, f"예상치 못한 응답: {data[:200]}")
        try:
            s.sendall(b"stop_IRL\r")
            s.recv(4096)
        except Exception:
            pass
        return data
    except socket.timeout:
        raise HTTPException(408, "학습 시간 초과 (iTach)")
    finally:
        s.close()


def _learn(timeout_sec: int) -> str:
    if IR_BACKEND == "broadlink":
        return _learn_via_broadlink(timeout_sec)
    if IR_BACKEND == "itach-ilearner":
        return _learn_via_itach(timeout_sec)
    raise HTTPException(501, f"{IR_BACKEND} 백엔드는 학습을 지원하지 않습니다 (broadlink 또는 itach-ilearner 사용)")


# ──────────────────────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    info = {
        "status": "ok",
        "service": "ir-mcp",
        "backend": IR_BACKEND,
        "itach": f"{ITACH_HOST}:{ITACH_PORT}" if "itach" in IR_BACKEND else None,
        "broadlink": BROADLINK_HOST if IR_BACKEND == "broadlink" else None,
        "adb_target": ADB_TARGET if IR_BACKEND.startswith("adb") or IR_BACKEND.startswith("android") else None,
    }
    # ADB 백엔드는 연결 상태도 확인
    if IR_BACKEND in ("adb", "android-tv", "androidtv") and ADB_TARGET:
        try:
            out = subprocess.run(
                ["adb", "-s", ADB_TARGET, "get-state"],
                capture_output=True, text=True, timeout=5,
            )
            info["adb_state"] = out.stdout.strip() or "no-device"
        except Exception as e:
            info["adb_state"] = f"error: {e}"
    return info


def _autogen_android_tv_codeset() -> dict:
    """Android TV 표준 키맵을 ir-mcp 포맷으로 변환."""
    return {f"_meta": {"backend": "adb", "auto": True}} | {
        key: f"adb:keyevent:{code}" for key, code in ANDROID_TV_KEYEVENTS.items()
    }


@app.post("/codesets/android_tv/autogen")
def autogen_android_tv():
    """Android TV 표준 keyevent 매핑을 codeset JSON으로 자동 생성 (학습 불필요)."""
    if IR_BACKEND not in ("adb", "android-tv", "androidtv"):
        raise HTTPException(400, "IR_BACKEND=adb 일 때만 사용 가능")
    data = _autogen_android_tv_codeset()
    _save_codeset("android_tv", data)
    return {"codeset": "android_tv", "keys": len(ANDROID_TV_KEYEVENTS), "path": str(_codeset_path("android_tv"))}


@app.post("/send")
def send_key(req: IRKeyRequest):
    data = _load_codeset(req.codeset)
    code = data.get(req.key)
    if not code:
        raise HTTPException(404, f"key not found: {req.codeset}/{req.key}")
    try:
        resp = _send(code)
    except OSError as e:
        raise HTTPException(502, f"backend unreachable: {e}")
    return {"codeset": req.codeset, "key": req.key, "backend": IR_BACKEND, "response": resp}


@app.post("/learn")
def learn_key(req: IRLearnRequest):
    """리모컨의 키를 1회 학습하여 codeset JSON에 자동 저장."""
    code = _learn(req.timeout_sec)
    data = _load_codeset(req.codeset)
    data[req.key] = code
    _save_codeset(req.codeset, data)
    return {
        "codeset": req.codeset,
        "key": req.key,
        "backend": IR_BACKEND,
        "saved_chars": len(code),
        "preview": code[:80] + ("…" if len(code) > 80 else ""),
    }


@app.get("/codesets")
def list_codesets():
    if not CODESET_DIR.exists():
        return {"codesets": []}
    return {"codesets": sorted(p.stem for p in CODESET_DIR.glob("*.json"))}


@app.get("/codesets/{codeset}")
def get_codeset(codeset: str):
    data = _load_codeset(codeset)
    if not data:
        raise HTTPException(404, f"codeset not found: {codeset}")
    return {"codeset": codeset, "keys": sorted(k for k in data if not k.startswith("_"))}


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "send", "description": "IR 키 송신"},
            {"name": "learn", "description": "리모컨 키 학습 후 codeset 저장 (broadlink/itach-ilearner)"},
            {"name": "codesets", "description": "사용 가능한 codeset 목록"},
        ]
    }
