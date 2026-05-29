"""Incident MCP — 임의 영상 업로드 + 자동 오류 분석.

기존 TC 자동화(시나리오 ↔ expected 비교)와는 독립적인 free-form 분석 서비스.
운영자가 KT/SKB 입찰 영상 / 고객 제보 영상 등을 시나리오 없이 즉시 분석.

엔드포인트:
  POST /analyze            — 영상 업로드 (multipart) → 분석 시작 → analysis_id 반환
  GET  /analyses           — 분석 목록 (최신 N건)
  GET  /analyses/{id}      — 분석 1건 상세 (verdict + incidents + 메타)
  GET  /analyses/{id}/thumbnails/{name}  — 썸네일 PNG 직접 다운로드
  GET  /analyses/{id}/report.json        — 원본 JSON
  GET  /health, /tools

내부 동작:
  업로드 → /data/analyses/<id>/source.mp4 저장 →
  백그라운드 thread에서 tools.video_analyzer.cli main(["analyze", ...]) 호출 →
  완료 시 status=done, 실패 시 status=failed (error_message 저장).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

# tools.video_analyzer 모듈을 동일 컨테이너에서 사용 — Dockerfile에서 tools/ 복사.
sys.path.insert(0, "/app")
from tools.video_analyzer.cli import main as analyzer_main  # noqa: E402

app = FastAPI(title="stb-incident-mcp")

DATA_DIR = Path(os.getenv("INCIDENT_DATA_DIR", "/data/analyses"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDING_MCP_URL = os.getenv("EMBEDDING_MCP_URL")  # 옵션 — 있으면 vision 보강

# 메모리 캐시 (디스크가 정원본)
STATE: dict[str, dict] = {}


def _status_path(aid: str) -> Path:
    return DATA_DIR / aid / "status.json"


def _write_status(aid: str, state: dict) -> None:
    p = _status_path(aid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE[aid] = state


def _load_status(aid: str) -> dict | None:
    if aid in STATE:
        return STATE[aid]
    p = _status_path(aid)
    if not p.exists():
        return None
    state = json.loads(p.read_text(encoding="utf-8"))
    STATE[aid] = state
    return state


def _run_analysis(aid: str, video_path: Path, interval: float, label: str | None) -> None:
    """백그라운드 작업 — CLI를 in-process로 호출."""
    work_dir = DATA_DIR / aid
    report_path = work_dir / "report.json"
    thumb_dir = work_dir / "thumbnails"
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state = {
        "id": aid,
        "label": label,
        "status": "running",
        "started_at": started_at,
        "video": str(video_path),
    }
    _write_status(aid, state)

    argv = [
        "analyze",
        "--video", str(video_path),
        "--output", str(report_path),
        "--interval", str(interval),
        "--thumbnails", str(thumb_dir),
    ]
    if EMBEDDING_MCP_URL:
        argv.extend(["--embedding-mcp-url", EMBEDDING_MCP_URL])

    try:
        rc = analyzer_main(argv)
    except Exception as e:  # noqa: BLE001
        state.update({"status": "failed", "error": str(e)[:500],
                      "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        _write_status(aid, state)
        return

    if rc != 0 or not report_path.exists():
        state.update({"status": "failed", "error": f"analyzer rc={rc}",
                      "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        _write_status(aid, state)
        return

    report = json.loads(report_path.read_text(encoding="utf-8"))
    state.update({
        "status": "done",
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": report["summary"],
        "video_meta": report["video"],
    })
    _write_status(aid, state)


# ──────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "incident-mcp",
        "data_dir": str(DATA_DIR),
        "vision_provider": "embedding-mcp" if EMBEDDING_MCP_URL else "off",
    }


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    label: str | None = Form(None),
    interval: float = Form(1.0),
):
    """영상 업로드 → 백그라운드 분석 시작 → analysis_id 반환."""
    if not file.filename or not file.filename.lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".webm")):
        raise HTTPException(400, "지원 포맷: mp4 / avi / mov / mkv / webm")

    aid = f"vid-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    work_dir = DATA_DIR / aid
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / f"source{Path(file.filename).suffix.lower()}"

    # 청크 저장
    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    th = threading.Thread(target=_run_analysis, args=(aid, target, interval, label), daemon=True)
    th.start()
    return {
        "analysis_id": aid,
        "label": label,
        "status": "queued",
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


@app.get("/analyses")
def list_analyses(limit: int = 50):
    """최신 N건 — 디스크의 status.json 스캔."""
    items: list[dict] = []
    for d in sorted(DATA_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        s = _load_status(d.name)
        if s:
            items.append({
                "id": s["id"],
                "label": s.get("label"),
                "status": s["status"],
                "started_at": s.get("started_at"),
                "finished_at": s.get("finished_at"),
                "summary": s.get("summary"),
            })
        if len(items) >= limit:
            break
    return {"analyses": items, "total": len(items)}


@app.get("/analyses/{aid}")
def get_analysis(aid: str):
    s = _load_status(aid)
    if not s:
        raise HTTPException(404, f"unknown analysis: {aid}")
    return s


@app.get("/analyses/{aid}/report.json")
def get_report(aid: str):
    p = DATA_DIR / aid / "report.json"
    if not p.exists():
        raise HTTPException(404, f"report not ready: {aid}")
    return FileResponse(p, media_type="application/json")


@app.get("/analyses/{aid}/thumbnails/{name}")
def get_thumbnail(aid: str, name: str):
    # path traversal 방지
    if "/" in name or ".." in name or not name.endswith(".png"):
        raise HTTPException(400, "invalid thumbnail name")
    p = DATA_DIR / aid / "thumbnails" / name
    if not p.exists():
        raise HTTPException(404, "thumbnail not found")
    return FileResponse(p, media_type="image/png")


@app.delete("/analyses/{aid}")
def delete_analysis(aid: str):
    d = DATA_DIR / aid
    if not d.exists():
        raise HTTPException(404, f"unknown analysis: {aid}")
    shutil.rmtree(d)
    STATE.pop(aid, None)
    return JSONResponse({"deleted": aid})


@app.get("/tools")
def list_tools():
    """MCP-compatible tool descriptor."""
    return {
        "tools": [
            {"name": "analyze", "description": "영상 업로드 → free-form 오류 자동 분석",
             "parameters": {"file": "video binary", "label": "str?", "interval": "float?"}},
            {"name": "list_analyses", "description": "최근 분석 목록"},
            {"name": "get_analysis", "description": "분석 1건 상세 + verdict + incidents"},
        ]
    }
