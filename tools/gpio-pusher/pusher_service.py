"""GPIO Pusher Service — Raspberry Pi 4 + PCA9685 + 서보로 BT 페어링 버튼 자동 누름.

라즈베리파이4 host network로 실행. systemd로 자동 시작.

배치:
  scp tools/gpio-pusher/* pi@gpio-pusher.local:/opt/gpio-pusher/
  ssh pi@gpio-pusher.local
    cd /opt/gpio-pusher
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    sudo systemctl enable --now gpio-pusher
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Adafruit PCA9685 - Pi가 아니면 mock으로 동작 (개발 환경 호환)
_pca = None
_mock = False
try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    _i2c = busio.I2C(board.SCL, board.SDA)
    _pca = PCA9685(_i2c)
    _pca.frequency = 50  # 서보 표준 50Hz
except (ImportError, NotImplementedError, Exception):
    _mock = True


# ────────────────────────────────────────────────────────────
# 서보 PWM 계산
# ────────────────────────────────────────────────────────────

def _angle_to_duty(angle: float) -> int:
    """0~180도 → PCA9685 16비트 duty cycle (50Hz, 1~2ms)."""
    # SG90: 1ms = 0도, 1.5ms = 90도, 2ms = 180도. 50Hz → 20ms 주기
    # PCA9685 duty = (pulse_ms / 20.0) * 65535
    pulse_ms = 1.0 + (angle / 180.0)  # 1.0~2.0 ms
    duty = int((pulse_ms / 20.0) * 65535)
    return max(0, min(65535, duty))


def _set_angle(channel: int, angle: float):
    if _mock or _pca is None:
        return  # mock 모드: 로그만
    if not (0 <= channel <= 15):
        raise HTTPException(400, f"channel out of range: {channel}")
    _pca.channels[channel].duty_cycle = _angle_to_duty(angle)


def _press(channel: int, press_angle: float = 90, rest_angle: float = 0, duration: float = 3.0):
    """버튼 누름 시퀀스: rest → press → 유지 → rest."""
    _set_angle(channel, press_angle)
    time.sleep(duration)
    _set_angle(channel, rest_angle)


# ────────────────────────────────────────────────────────────
# API
# ────────────────────────────────────────────────────────────

class PressRequest(BaseModel):
    channel: int = Field(..., ge=0, le=15)
    duration: float = Field(3.0, gt=0, le=30)
    press_angle: float = Field(90, ge=0, le=180)
    rest_angle: float = Field(0, ge=0, le=180)


class MultiPressRequest(BaseModel):
    """여러 채널 동시 누름 (예: OK + 뒤로가기)."""
    channels: list[int] = Field(..., min_length=1, max_length=16)
    duration: float = Field(5.0, gt=0, le=30)
    press_angle: float = Field(90, ge=0, le=180)
    rest_angle: float = Field(0, ge=0, le=180)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # 종료 시 모든 채널 rest
    if _pca and not _mock:
        for ch in range(16):
            _pca.channels[ch].duty_cycle = 0


app = FastAPI(title="gpio-pusher", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "gpio-pusher",
        "mode": "mock" if _mock else "hardware",
        "channels": 16,
    }


@app.post("/press")
def press(req: PressRequest):
    _press(req.channel, req.press_angle, req.rest_angle, req.duration)
    return {"channel": req.channel, "duration": req.duration, "mode": "mock" if _mock else "hardware"}


@app.post("/multi_press")
def multi_press(req: MultiPressRequest):
    """여러 채널을 동시에 press_angle로 이동 후 duration 유지, 다시 rest."""
    for ch in req.channels:
        _set_angle(ch, req.press_angle)
    time.sleep(req.duration)
    for ch in req.channels:
        _set_angle(ch, req.rest_angle)
    return {"channels": req.channels, "duration": req.duration, "mode": "mock" if _mock else "hardware"}


@app.post("/release_all")
def release_all():
    """안전 — 모든 채널을 rest 각도로."""
    if _pca and not _mock:
        for ch in range(16):
            _pca.channels[ch].duty_cycle = 0
    return {"released": True}


@app.get("/tools")
def tools():
    return {
        "tools": [
            {"name": "press", "description": "단일 채널 버튼 누름"},
            {"name": "multi_press", "description": "다중 채널 동시 누름 (조합 키)"},
            {"name": "release_all", "description": "모든 채널 안전 정지"},
        ]
    }
