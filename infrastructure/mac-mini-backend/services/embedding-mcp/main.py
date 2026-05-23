"""Embedding MCP — 호스트 네이티브 Ollama로 텍스트/비전 임베딩 생성."""
import base64
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-embedding-mcp")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
VISION_MODEL = os.getenv("VISION_MODEL", "llava:latest")


class TextEmbedRequest(BaseModel):
    text: str


class VisionDescribeRequest(BaseModel):
    image_base64: str
    prompt: str = "Describe what's on this STB screen in detail, focusing on UI elements."


@app.get("/health")
def health():
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return {"status": "ok", "ollama": "reachable", "models": r.json().get("models", [])}
    except httpx.HTTPError as e:
        return {"status": "degraded", "ollama_error": str(e)}


@app.post("/text")
def embed_text(req: TextEmbedRequest):
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBEDDING_MODEL, "prompt": req.text},
            timeout=30,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"ollama failed: {e}")
    return {"model": EMBEDDING_MODEL, "embedding": r.json()["embedding"]}


@app.post("/vision/describe")
def describe_image(req: VisionDescribeRequest):
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": VISION_MODEL,
                "prompt": req.prompt,
                "images": [req.image_base64],
                "stream": False,
            },
            timeout=120,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"ollama vision failed: {e}")
    return {"model": VISION_MODEL, "description": r.json()["response"]}


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "text", "description": "텍스트 임베딩 생성 (로그/시나리오)"},
            {"name": "vision/describe", "description": "STB 화면 캡처를 자연어로 묘사"},
        ]
    }
