"""Detection MCP — DUT 캡처를 베이스라인과 비교, 이상치 판정."""
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-detection-mcp")

BASELINE_URL = os.getenv("BASELINE_URL", "http://baseline-mcp:8000")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://embedding-mcp:8000")
THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.92"))


class ScreenCheckRequest(BaseModel):
    scenario: str
    image_base64: str
    firmware: str | None = None


class LogCheckRequest(BaseModel):
    scenario: str
    log_text: str
    firmware: str | None = None


def _check_against_baseline(collection: str, vector: list[float], scenario: str) -> dict:
    r = httpx.post(
        f"{BASELINE_URL}/query",
        json={"collection": collection, "vector": vector, "scenario": scenario, "top_k": 1},
        timeout=10,
    )
    r.raise_for_status()
    hits = r.json()["hits"]
    if not hits:
        return {"verdict": "no_baseline", "best_score": 0.0, "hint": "베이스라인 등록 필요"}
    top = hits[0]
    is_anomaly = top["score"] < THRESHOLD
    return {
        "verdict": "anomaly" if is_anomaly else "normal",
        "best_score": top["score"],
        "threshold": THRESHOLD,
        "baseline_payload": top["payload"],
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "detection-mcp", "threshold": THRESHOLD}


@app.post("/check/screen")
def check_screen(req: ScreenCheckRequest):
    # 1) 이미지를 비전 모델 묘사 → 텍스트 임베딩
    desc_r = httpx.post(
        f"{EMBEDDING_URL}/vision/describe",
        json={"image_base64": req.image_base64},
        timeout=180,
    )
    desc_r.raise_for_status()
    description = desc_r.json()["description"]

    emb_r = httpx.post(f"{EMBEDDING_URL}/text", json={"text": description}, timeout=30)
    emb_r.raise_for_status()
    vector = emb_r.json()["embedding"]

    result = _check_against_baseline("screen", vector, req.scenario)
    result["description"] = description
    return result


@app.post("/check/log")
def check_log(req: LogCheckRequest):
    emb_r = httpx.post(f"{EMBEDDING_URL}/text", json={"text": req.log_text}, timeout=30)
    emb_r.raise_for_status()
    vector = emb_r.json()["embedding"]
    return _check_against_baseline("log", vector, req.scenario)


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "check/screen", "description": "DUT 화면을 베이스라인과 비교"},
            {"name": "check/log", "description": "DUT 로그를 베이스라인과 비교"},
        ]
    }
