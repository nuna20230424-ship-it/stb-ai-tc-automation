"""Voice MCP — TTS 생성 + 스피커 재생 (STB 마이크 또는 BT 음성 리모컨 대상).

흐름: text → pyttsx3로 WAV 저장 → aplay/afplay로 재생 (host 스피커).
재생 종료 시각을 정확히 반환하여 응답 지연 측정에 사용.
"""
from __future__ import annotations

import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pyttsx3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-voice-mcp")

OUTPUT_DIR = Path(os.getenv("VOICE_OUTPUT_DIR", "/data/voice"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_RATE = int(os.getenv("VOICE_RATE", "175"))
DEFAULT_VOLUME = float(os.getenv("VOICE_VOLUME", "1.0"))
PLAYBACK_CMD = os.getenv("PLAYBACK_CMD", "aplay")  # macOS는 'afplay' 권장


class SpeakRequest(BaseModel):
    text: str
    rate: int | None = None
    volume: float | None = None
    voice_id: str | None = None    # 시스템 의존 voice id
    save_only: bool = False        # True면 WAV만 생성, 재생 X


def _synthesize(text: str, rate: int, volume: float, voice_id: str | None) -> Path:
    out = OUTPUT_DIR / f"tts-{uuid.uuid4().hex[:8]}.wav"
    engine = pyttsx3.init()
    engine.setProperty("rate", rate)
    engine.setProperty("volume", volume)
    if voice_id:
        engine.setProperty("voice", voice_id)
    engine.save_to_file(text, str(out))
    engine.runAndWait()
    return out


def _play(wav_path: Path) -> tuple[float, float]:
    """WAV 재생. (start_epoch, end_epoch) 반환."""
    start = time.time()
    try:
        subprocess.run([PLAYBACK_CMD, str(wav_path)], check=True, capture_output=True, timeout=60)
    except FileNotFoundError:
        raise HTTPException(500, f"playback cmd not found: {PLAYBACK_CMD}")
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"playback failed: {e.stderr.decode()[:200]}")
    end = time.time()
    return start, end


@app.get("/health")
def health():
    try:
        engine = pyttsx3.init()
        voices = [{"id": v.id, "name": v.name, "lang": getattr(v, "languages", None)}
                  for v in engine.getProperty("voices")][:5]
    except Exception as e:
        voices = []
        return {"status": "degraded", "error": str(e)}
    return {"status": "ok", "service": "voice-mcp", "voices_sample": voices, "playback": PLAYBACK_CMD}


@app.post("/speak")
def speak(req: SpeakRequest):
    wav = _synthesize(
        req.text,
        req.rate or DEFAULT_RATE,
        req.volume if req.volume is not None else DEFAULT_VOLUME,
        req.voice_id,
    )
    if req.save_only:
        return {"wav_path": str(wav), "played": False}

    start, end = _play(wav)
    return {
        "wav_path": str(wav),
        "played": True,
        "started_at": datetime.fromtimestamp(start, tz=timezone.utc).isoformat(),
        "ended_at": datetime.fromtimestamp(end, tz=timezone.utc).isoformat(),
        "duration_ms": int((end - start) * 1000),
        "end_epoch": end,  # 응답 지연 측정 기준
    }


@app.post("/play_file")
def play_file(path: str):
    wav = Path(path)
    if not wav.exists():
        raise HTTPException(404, f"file not found: {path}")
    start, end = _play(wav)
    return {"played": True, "end_epoch": end, "duration_ms": int((end - start) * 1000)}


@app.get("/voices")
def list_voices():
    engine = pyttsx3.init()
    return {"voices": [{"id": v.id, "name": v.name} for v in engine.getProperty("voices")]}


@app.get("/tools")
def tools():
    return {
        "tools": [
            {"name": "speak", "description": "텍스트를 TTS로 합성하여 스피커로 재생"},
            {"name": "play_file", "description": "기존 WAV 파일 재생"},
            {"name": "voices", "description": "사용 가능한 voice 목록"},
        ]
    }
