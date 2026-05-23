"""IR MCP — Global Caché iTach IP2IR(TCP 4998) 래퍼."""
import json
import os
import socket
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-ir-mcp")

ITACH_HOST = os.getenv("ITACH_HOST", "10.0.10.20")
ITACH_PORT = int(os.getenv("ITACH_PORT", "4998"))
CODESET_DIR = Path(os.getenv("IR_CODESET_DIR", "/data/ir-codesets"))


class IRKeyRequest(BaseModel):
    codeset: str  # 예: "ref_remote" or "vendor_x"
    key: str      # 예: "POWER", "CH_UP", "OK"


def _load_code(codeset: str, key: str) -> str:
    """codeset JSON에서 globalcache 포맷 IR 시퀀스 로딩."""
    path = CODESET_DIR / f"{codeset}.json"
    if not path.exists():
        raise HTTPException(404, f"codeset not found: {codeset}")
    data = json.loads(path.read_text())
    if key not in data:
        raise HTTPException(404, f"key not found in codeset: {key}")
    return data[key]


def _send_itach(payload: str) -> str:
    """iTach에 한 줄 명령 전송 후 응답 수신."""
    with socket.create_connection((ITACH_HOST, ITACH_PORT), timeout=3) as s:
        s.sendall((payload + "\r").encode())
        return s.recv(4096).decode().strip()


@app.get("/health")
def health():
    return {"status": "ok", "service": "ir-mcp", "itach": f"{ITACH_HOST}:{ITACH_PORT}"}


@app.post("/send")
def send_key(req: IRKeyRequest):
    code = _load_code(req.codeset, req.key)
    # iTach sendir 포맷: sendir,<module>:<port>,<id>,<freq>,<repeat>,<offset>,<pulses>
    try:
        resp = _send_itach(code)
    except OSError as e:
        raise HTTPException(502, f"iTach unreachable: {e}")
    return {"codeset": req.codeset, "key": req.key, "itach_response": resp}


@app.get("/codesets")
def list_codesets():
    if not CODESET_DIR.exists():
        return {"codesets": []}
    return {"codesets": sorted(p.stem for p in CODESET_DIR.glob("*.json"))}


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "send", "description": "iTach로 IR 키 송신",
             "parameters": {"codeset": "str", "key": "str"}},
            {"name": "codesets", "description": "사용 가능한 codeset 목록"},
        ]
    }
