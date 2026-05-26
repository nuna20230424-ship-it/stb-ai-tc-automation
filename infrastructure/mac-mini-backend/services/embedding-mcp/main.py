"""Embedding MCP — 텍스트 임베딩 + 4종 vision provider 라우팅.

vision provider 다변화 (Phase 2):
  VISION_PROVIDER ∈ {"ollama"(기본) | "anthropic" | "openai" | "gemini"}
  provider별 API 키는 환경변수로 주입. SDK는 lazy import (필요 provider만).

bench 도구는 tools/vision_bench/ — 동일 추상화로 골든셋 기반 모델 선정.
"""
import base64
import os
import time

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-embedding-mcp")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# vision provider 라우팅
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "ollama").lower()
VISION_MODEL = os.getenv("VISION_MODEL", "llava:latest")
ANTHROPIC_VISION_MODEL = os.getenv("ANTHROPIC_VISION_MODEL", "claude-sonnet-4-6")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")


class TextEmbedRequest(BaseModel):
    text: str


class VisionDescribeRequest(BaseModel):
    image_base64: str
    prompt: str = "Describe what's on this STB screen in detail, focusing on UI elements."


@app.get("/health")
def health():
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_status = {"ollama": "reachable", "models": r.json().get("models", [])}
    except httpx.HTTPError as e:
        ollama_status = {"ollama": "unreachable", "ollama_error": str(e)}
    return {
        "status": "ok",
        "vision_provider": VISION_PROVIDER,
        "vision_model": _active_vision_model(),
        **ollama_status,
    }


def _active_vision_model() -> str:
    return {
        "ollama":    VISION_MODEL,
        "anthropic": ANTHROPIC_VISION_MODEL,
        "openai":    OPENAI_VISION_MODEL,
        "gemini":    GEMINI_VISION_MODEL,
    }.get(VISION_PROVIDER, VISION_MODEL)


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


# ──────────────────────────────────────────────────────────────
# Vision provider 분기 (SDK는 lazy import)
# ──────────────────────────────────────────────────────────────

def _describe_ollama(image_b64: str, prompt: str) -> dict:
    r = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": VISION_MODEL, "prompt": prompt,
               "images": [image_b64], "stream": False},
        timeout=180,
    )
    r.raise_for_status()
    body = r.json()
    return {
        "model": VISION_MODEL, "provider": "ollama",
        "description": body.get("response", ""),
        "tokens_in": body.get("prompt_eval_count", 0),
        "tokens_out": body.get("eval_count", 0),
    }


def _describe_anthropic(image_b64: str, prompt: str) -> dict:
    try:
        from anthropic import Anthropic
    except ImportError:
        raise HTTPException(503, "anthropic SDK 미설치 — requirements.txt 확인")
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise HTTPException(503, "ANTHROPIC_API_KEY 미설정")
    client = Anthropic(api_key=key)
    resp = client.messages.create(
        model=ANTHROPIC_VISION_MODEL,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": image_b64,
                }},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    text = "".join(getattr(b, "text", "") for b in resp.content)
    return {
        "model": ANTHROPIC_VISION_MODEL, "provider": "anthropic",
        "description": text,
        "tokens_in": resp.usage.input_tokens,
        "tokens_out": resp.usage.output_tokens,
    }


def _describe_openai(image_b64: str, prompt: str) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        raise HTTPException(503, "openai SDK 미설치 — requirements.txt 확인")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(503, "OPENAI_API_KEY 미설정")
    client = OpenAI(api_key=key)
    resp = client.chat.completions.create(
        model=OPENAI_VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ],
        }],
        max_tokens=512,
    )
    return {
        "model": OPENAI_VISION_MODEL, "provider": "openai",
        "description": resp.choices[0].message.content or "",
        "tokens_in": resp.usage.prompt_tokens,
        "tokens_out": resp.usage.completion_tokens,
    }


def _describe_gemini(image_b64: str, prompt: str) -> dict:
    try:
        from google import genai
    except ImportError:
        raise HTTPException(503, "google-genai SDK 미설치 — requirements.txt 확인")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise HTTPException(503, "GEMINI_API_KEY 또는 GOOGLE_API_KEY 미설정")
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model=GEMINI_VISION_MODEL,
        contents=[{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
            ],
        }],
    )
    usage = resp.usage_metadata
    return {
        "model": GEMINI_VISION_MODEL, "provider": "gemini",
        "description": resp.text or "",
        "tokens_in": getattr(usage, "prompt_token_count", 0),
        "tokens_out": getattr(usage, "candidates_token_count", 0),
    }


_PROVIDER_DISPATCH = {
    "ollama":    _describe_ollama,
    "anthropic": _describe_anthropic,
    "openai":    _describe_openai,
    "gemini":    _describe_gemini,
}


@app.post("/vision/describe")
def describe_image(req: VisionDescribeRequest):
    fn = _PROVIDER_DISPATCH.get(VISION_PROVIDER)
    if fn is None:
        raise HTTPException(500, f"알 수 없는 VISION_PROVIDER: {VISION_PROVIDER}")
    t0 = time.perf_counter()
    try:
        result = fn(req.image_base64, req.prompt)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"{VISION_PROVIDER} vision failed: {e}")
    result["latency_ms"] = (time.perf_counter() - t0) * 1000
    return result


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "text", "description": "텍스트 임베딩 생성 (로그/시나리오)"},
            {"name": "vision/describe",
             "description": f"STB 화면 자연어 묘사 (provider={VISION_PROVIDER})"},
        ]
    }
