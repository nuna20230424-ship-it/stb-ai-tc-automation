"""Precondition 매크로 단위 smoke test.

목적:
- 각 reach_*() 매크로가 시나리오와 무관하게 단독으로 동작하는지 검증
- 디바이스 입고 후 매크로별 디버깅 진입점 제공
- 새 매크로 추가 시 회귀 잡기

각 테스트는 매크로 도달 → 캡처 → 비어있지 않은 프레임만 확인 (시나리오 detection은
별도 baseline 등록이 필요하므로 smoke 단계에서는 frame 존재만 가드).

마커: -m preconditions 로 단독 실행 가능.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pytest
from influxdb_client import Point, WritePrecision

from utils import extract_middle_frame


# ──────────────────────────────────────────────────────────────
# helper: 매크로 도달 후 캡처 + 프레임 존재 확인 + 메트릭 기록
# ──────────────────────────────────────────────────────────────

def _smoke_assert(name: str, gateway, metrics, env, settle_sec: float = 1.5):
    """매크로 도달 후 캡처해 프레임이 정상 추출되는지만 확인."""
    time.sleep(settle_sec)
    t0 = time.monotonic()
    cap = gateway.capture.capture("dut", duration_sec=env["capture_duration_sec"],
                                  label=f"precond_{name}")
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    frame = extract_middle_frame(Path(cap["path"]))
    assert frame.exists() and frame.stat().st_size > 0, f"{name}: 빈 프레임"

    point = (Point("precondition_smoke")
             .tag("precondition", name)
             .tag("firmware", env["firmware"])
             .field("capture_ms", elapsed_ms)
             .time(datetime.utcnow(), WritePrecision.NS))
    metrics.write_api.write(bucket=metrics.bucket, org=metrics.org, record=point)


# ──────────────────────────────────────────────────────────────
# 기반 상태
# ──────────────────────────────────────────────────────────────

@pytest.mark.preconditions
def test_home_screen(pre_home_screen, gateway, metrics, env):
    assert pre_home_screen["state"] == "home_screen"
    _smoke_assert("home_screen", gateway, metrics, env)


# ──────────────────────────────────────────────────────────────
# Live TV / EPG
# ──────────────────────────────────────────────────────────────

@pytest.mark.preconditions
def test_live_tv(pre_live_tv, gateway, metrics, env):
    assert pre_live_tv["state"] == "live_tv"
    _smoke_assert("live_tv", gateway, metrics, env)


@pytest.mark.preconditions
def test_epg_open(pre_epg_open, gateway, metrics, env):
    assert pre_epg_open["state"] == "epg_open"
    _smoke_assert("epg_open", gateway, metrics, env)


# ──────────────────────────────────────────────────────────────
# Netflix chain (secrets 누락 시 fixture 단계에서 skip)
# ──────────────────────────────────────────────────────────────

@pytest.mark.preconditions
@pytest.mark.ott
def test_netflix_logged_in(pre_netflix_logged_in, gateway, metrics, env):
    assert pre_netflix_logged_in["state"] == "netflix_logged_in"
    _smoke_assert("netflix_logged_in", gateway, metrics, env, settle_sec=2.0)


@pytest.mark.preconditions
@pytest.mark.ott
def test_netflix_home(pre_netflix_home, gateway, metrics, env):
    assert pre_netflix_home["state"] == "netflix_home"
    _smoke_assert("netflix_home", gateway, metrics, env)


@pytest.mark.preconditions
@pytest.mark.ott
@pytest.mark.slow
def test_netflix_playing(pre_netflix_playing, gateway, metrics, env):
    assert pre_netflix_playing["state"] == "netflix_playing"
    _smoke_assert("netflix_playing", gateway, metrics, env, settle_sec=3.0)


# ──────────────────────────────────────────────────────────────
# Tving
# ──────────────────────────────────────────────────────────────

@pytest.mark.preconditions
@pytest.mark.ott
def test_tving_logged_in(pre_tving_logged_in, gateway, metrics, env):
    assert pre_tving_logged_in["state"] == "tving_logged_in"
    _smoke_assert("tving_logged_in", gateway, metrics, env, settle_sec=2.0)


# ──────────────────────────────────────────────────────────────
# VOD / DRM
# ──────────────────────────────────────────────────────────────

@pytest.mark.preconditions
@pytest.mark.slow
def test_playback_active(pre_playback_active, gateway, metrics, env):
    assert pre_playback_active["state"] in ("playback_active", "live_tv")
    _smoke_assert("playback_active", gateway, metrics, env, settle_sec=2.0)


@pytest.mark.preconditions
@pytest.mark.slow
def test_vod_playing(pre_vod_playing, gateway, metrics, env):
    # alias of playback_active
    assert pre_vod_playing["state"] in ("playback_active", "live_tv")
    _smoke_assert("vod_playing", gateway, metrics, env, settle_sec=2.0)


@pytest.mark.preconditions
@pytest.mark.drm
@pytest.mark.slow
def test_drm_content_playing(pre_drm_content_playing, gateway, metrics, env):
    assert pre_drm_content_playing["state"] == "drm_content_playing"
    _smoke_assert("drm_content_playing", gateway, metrics, env, settle_sec=3.0)


# ──────────────────────────────────────────────────────────────
# 환경 확인 (도달 매크로 아님 — env flag만 체크)
# ──────────────────────────────────────────────────────────────

@pytest.mark.preconditions
@pytest.mark.drm
def test_hdcp_unsupported_display(pre_hdcp_unsupported_display):
    assert pre_hdcp_unsupported_display["state"] == "hdcp_unsupported_display"
    assert pre_hdcp_unsupported_display["available"] is True
