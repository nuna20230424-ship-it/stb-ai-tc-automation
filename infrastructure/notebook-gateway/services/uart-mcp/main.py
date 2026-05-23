"""UART MCP — FTDI USB-Serial 로그 수집기.

세션을 열어 백그라운드 스레드가 로그를 파일에 누적, REST로 tail/stop 제공.
"""
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import serial
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-uart-mcp")

DEVICES = {
    "ref": os.getenv("REF_UART_DEVICE", "/dev/ttyUSB0"),
    "dut": os.getenv("DUT_UART_DEVICE", "/dev/ttyUSB1"),
}
BAUD = int(os.getenv("UART_BAUD", "115200"))
LOG_DIR = Path(os.getenv("LOG_OUTPUT_DIR", "/data/uart-logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

_sessions: dict[str, dict] = {}


class StartSessionRequest(BaseModel):
    target: str  # "ref" | "dut"
    label: str | None = None


def _reader_thread(session_id: str, device: str, log_path: Path, stop_flag: threading.Event):
    try:
        with serial.Serial(device, BAUD, timeout=1) as ser, log_path.open("ab") as f:
            while not stop_flag.is_set():
                data = ser.read(1024)
                if data:
                    f.write(data)
                    f.flush()
                else:
                    time.sleep(0.05)
    except Exception as e:
        log_path.with_suffix(".error").write_text(f"reader error: {e}\n")


@app.get("/health")
def health():
    return {"status": "ok", "service": "uart-mcp", "devices": DEVICES}


@app.post("/sessions")
def start_session(req: StartSessionRequest):
    if req.target not in DEVICES:
        raise HTTPException(400, "target must be 'ref' or 'dut'")
    device = DEVICES[req.target]
    session_id = f"{req.label or req.target}-{uuid.uuid4().hex[:8]}"
    log_path = LOG_DIR / f"{session_id}-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.log"
    stop_flag = threading.Event()
    thread = threading.Thread(target=_reader_thread, args=(session_id, device, log_path, stop_flag), daemon=True)
    thread.start()
    _sessions[session_id] = {"thread": thread, "stop": stop_flag, "log": log_path, "device": device}
    return {"session_id": session_id, "log_path": str(log_path)}


@app.delete("/sessions/{session_id}")
def stop_session(session_id: str):
    sess = _sessions.pop(session_id, None)
    if not sess:
        raise HTTPException(404, "session not found")
    sess["stop"].set()
    sess["thread"].join(timeout=5)
    return {"session_id": session_id, "log_path": str(sess["log"])}


@app.get("/sessions/{session_id}/tail")
def tail(session_id: str, lines: int = 200):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "session not found")
    log_path: Path = sess["log"]
    if not log_path.exists():
        return {"lines": []}
    content = log_path.read_bytes().decode(errors="replace").splitlines()
    return {"lines": content[-lines:]}


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "start_session", "description": "UART 로그 수집 세션 시작"},
            {"name": "stop_session", "description": "세션 종료"},
            {"name": "tail", "description": "수집 중 로그 마지막 N줄 조회"},
        ]
    }
