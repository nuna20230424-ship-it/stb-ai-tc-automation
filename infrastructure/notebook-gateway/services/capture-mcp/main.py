"""Capture MCP — HDMI 캡처카드 제어 (FFmpeg 기반).

Sprint 1에 실제 캡처/업로드 로직 구현. 현재는 스켈레톤.
"""
import os
import subprocess
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-capture-mcp")

REF_DEVICE = os.getenv("REF_CAPTURE_DEVICE", "/dev/video0")
DUT_DEVICE = os.getenv("DUT_CAPTURE_DEVICE", "/dev/video2")
OUTPUT_DIR = Path(os.getenv("CAPTURE_OUTPUT_DIR", "/data/captures"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class CaptureRequest(BaseModel):
    target: str  # "ref" | "dut"
    duration_sec: int = 5
    label: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "capture-mcp"}


@app.get("/devices")
def list_devices():
    return {"ref": REF_DEVICE, "dut": DUT_DEVICE}


@app.post("/capture")
def capture(req: CaptureRequest):
    device = REF_DEVICE if req.target == "ref" else DUT_DEVICE
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


@app.get("/tools")
def list_tools():
    """MCP-compatible tool descriptor (placeholder)."""
    return {
        "tools": [
            {"name": "capture", "description": "STB HDMI 영상을 N초간 캡처",
             "parameters": {"target": "ref|dut", "duration_sec": "int", "label": "str?"}},
            {"name": "list_devices", "description": "사용 가능한 캡처 디바이스 목록"},
        ]
    }
