"""Capture MCP — HDMI 캡처카드 제어 (FFmpeg 기반).

엔드포인트:
  POST   /capture                  — 동기 N초 캡처 (기존, 짧은 프레임용)
  POST   /capture/start            — 비동기 영상 녹화 시작 → session_id 반환
  GET    /capture/sessions          — 활성 세션 목록
  DELETE /capture/sessions/{sid}    — 녹화 종료 + mp4 경로 반환 (증빙 다운로드용)
  GET    /devices, /health, /tools

영상 녹화 흐름 (시나리오 1건당):
  start_capture(scenario_id) → ffmpeg Popen 백그라운드 → IR/UART/검증 단계 진행 →
  stop_capture(sid) → 'q' 입력으로 ffmpeg graceful 종료 → mp4 path 회수.

duration_sec=0 으로 /capture/start 호출 시 무제한 (stop 호출 전까지 녹화).
"""
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-capture-mcp")

REF_DEVICE = os.getenv("REF_CAPTURE_DEVICE", "/dev/video0")
DUT_DEVICE = os.getenv("DUT_CAPTURE_DEVICE", "/dev/video2")
OUTPUT_DIR = Path(os.getenv("CAPTURE_OUTPUT_DIR", "/data/captures"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 활성 녹화 세션 — {sid: {proc, path, target, started_at, scenario_id}}
SESSIONS: dict[str, dict] = {}


class CaptureRequest(BaseModel):
    target: str  # "ref" | "dut"
    duration_sec: int = 5
    label: str | None = None


class RecordStartRequest(BaseModel):
    target: Literal["ref", "dut"] = "dut"
    scenario_id: str
    max_duration_sec: int = 120  # safety cap — stop 누락 시 강제 종료
    label: str | None = None


def _device_for(target: str) -> str:
    return REF_DEVICE if target == "ref" else DUT_DEVICE


@app.get("/health")
def health():
    return {"status": "ok", "service": "capture-mcp"}


@app.get("/devices")
def list_devices():
    return {"ref": REF_DEVICE, "dut": DUT_DEVICE}


@app.post("/capture")
def capture(req: CaptureRequest):
    device = _device_for(req.target)
    capture_id = f"{req.label or 'capture'}-{uuid.uuid4().hex[:8]}"
    output = OUTPUT_DIR / f"{capture_id}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "v4l2", "-i", device,
        "-t", str(req.duration_sec),
        "-c:v", "libx264", "-preset", "ultrafast",
        str(output),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=req.duration_sec + 30)
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"ffmpeg failed: {e.stderr.decode()[:500]}")

    return {"capture_id": capture_id, "path": str(output), "device": device}


@app.post("/capture/start")
def capture_start(req: RecordStartRequest):
    """비동기 영상 녹화 시작 — 시나리오 실행 전 호출, 끝나면 DELETE로 종료."""
    sid = f"rec-{req.scenario_id}-{uuid.uuid4().hex[:8]}"
    device = _device_for(req.target)
    output = OUTPUT_DIR / f"{sid}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "v4l2", "-i", device,
        "-t", str(req.max_duration_sec),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-loglevel", "warning",
        str(output),
    ]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        raise HTTPException(500, f"ffmpeg not installed: {e}")

    SESSIONS[sid] = {
        "proc": proc,
        "path": str(output),
        "target": req.target,
        "device": device,
        "scenario_id": req.scenario_id,
        "started_at": time.time(),
        "max_duration_sec": req.max_duration_sec,
    }
    return {"session_id": sid, "path": str(output), "device": device, "started_at": SESSIONS[sid]["started_at"]}


@app.get("/capture/sessions")
def list_sessions():
    out = []
    for sid, s in SESSIONS.items():
        out.append({
            "session_id": sid,
            "scenario_id": s["scenario_id"],
            "target": s["target"],
            "started_at": s["started_at"],
            "elapsed_sec": time.time() - s["started_at"],
            "alive": s["proc"].poll() is None,
        })
    return {"sessions": out}


@app.delete("/capture/sessions/{sid}")
def stop_session(sid: str):
    """녹화 종료 — ffmpeg에 'q'를 보내 graceful flush, 실패 시 SIGTERM 폴백."""
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, f"unknown session: {sid}")

    proc: subprocess.Popen = s["proc"]
    if proc.poll() is None:
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.write(b"q")
                proc.stdin.flush()
                proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    elapsed = time.time() - s["started_at"]
    output_path = Path(s["path"])
    size_bytes = output_path.stat().st_size if output_path.exists() else 0
    rc = proc.returncode
    SESSIONS.pop(sid, None)
    return {
        "session_id": sid,
        "path": s["path"],
        "scenario_id": s["scenario_id"],
        "elapsed_sec": round(elapsed, 2),
        "size_bytes": size_bytes,
        "ffmpeg_returncode": rc,
    }


@app.get("/tools")
def list_tools():
    """MCP-compatible tool descriptor."""
    return {
        "tools": [
            {"name": "capture", "description": "STB HDMI 영상을 N초간 동기 캡처",
             "parameters": {"target": "ref|dut", "duration_sec": "int", "label": "str?"}},
            {"name": "capture_start", "description": "비동기 영상 녹화 시작 (시나리오 증빙)",
             "parameters": {"target": "ref|dut", "scenario_id": "str", "max_duration_sec": "int"}},
            {"name": "stop_session", "description": "녹화 종료 — mp4 경로 반환",
             "parameters": {"session_id": "str"}},
            {"name": "list_devices", "description": "사용 가능한 캡처 디바이스 목록"},
        ]
    }
