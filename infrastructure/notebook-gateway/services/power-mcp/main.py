"""Power MCP — Shelly Smart Plug Gen2+ HTTP RPC 래퍼."""
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-power-mcp")

PLUGS = {
    "ref": os.getenv("REF_PLUG_HOST", "10.0.10.31"),
    "dut": os.getenv("DUT_PLUG_HOST", "10.0.10.32"),
}


class PowerRequest(BaseModel):
    target: str  # "ref" | "dut"
    on: bool


@app.get("/health")
def health():
    return {"status": "ok", "service": "power-mcp", "plugs": PLUGS}


@app.post("/set")
def set_power(req: PowerRequest):
    if req.target not in PLUGS:
        raise HTTPException(400, "target must be 'ref' or 'dut'")
    host = PLUGS[req.target]
    url = f"http://{host}/rpc/Switch.Set?id=0&on={'true' if req.on else 'false'}"
    try:
        r = httpx.get(url, timeout=3)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"shelly unreachable: {e}")
    return {"target": req.target, "on": req.on, "shelly_response": r.json()}


@app.post("/cycle")
def power_cycle(target: str, off_sec: int = 5):
    """전원 OFF→대기→ON. 하드 리셋 시나리오."""
    import time
    set_power(PowerRequest(target=target, on=False))
    time.sleep(off_sec)
    set_power(PowerRequest(target=target, on=True))
    return {"target": target, "cycled": True, "off_duration_sec": off_sec}


@app.get("/status/{target}")
def status(target: str):
    if target not in PLUGS:
        raise HTTPException(400, "target must be 'ref' or 'dut'")
    host = PLUGS[target]
    try:
        r = httpx.get(f"http://{host}/rpc/Switch.GetStatus?id=0", timeout=3)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"shelly unreachable: {e}")
    return r.json()


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "set", "description": "스마트플러그 ON/OFF",
             "parameters": {"target": "ref|dut", "on": "bool"}},
            {"name": "cycle", "description": "전원 리셋 (OFF→대기→ON)"},
            {"name": "status", "description": "현재 전원 상태"},
        ]
    }
