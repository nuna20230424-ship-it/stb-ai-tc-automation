"""STB precondition reach 매크로 — IR/voice 시퀀스로 알려진 상태에 도달.

매크로는 모두 idempotent: 어떤 화면에서 시작하든 HOME 리셋 → 목표 상태까지 진행.
fixtures.py가 이 매크로들을 pytest fixture로 래핑하고 의존성을 해결한다.
"""
from __future__ import annotations

import time
from typing import Any

# ──────────────────────────────────────────────────────────────
# 공통 helper
# ──────────────────────────────────────────────────────────────

def _ir(gateway, env, key: str, repeat: int = 1, wait: float = 0.15) -> None:
    for _ in range(repeat):
        gateway.ir.send(env["ir_codeset"], key)
        time.sleep(wait)


def _voice(gateway, utterance: str, settle: float = 2.5) -> None:
    gateway.voice.speak(utterance)
    time.sleep(settle)


# ──────────────────────────────────────────────────────────────
# 기반 상태
# ──────────────────────────────────────────────────────────────

def reach_home_screen(gateway, env) -> dict[str, Any]:
    """전원 ON 보장 → HOME 키 → 부팅 대기. 모든 매크로의 출발점."""
    gateway.power.set("dut", on=True)
    time.sleep(env.get("boot_wait_sec", 30) // 6)
    _ir(gateway, env, "HOME")
    time.sleep(1.5)
    return {"state": "home_screen"}


# ──────────────────────────────────────────────────────────────
# Live TV / EPG
# ──────────────────────────────────────────────────────────────

def reach_live_tv(gateway, env) -> dict[str, Any]:
    """HOME에서 LIVE 또는 CH 키로 라이브 채널 진입."""
    live_key = env.get("live_tv_key", "LIVE")
    _ir(gateway, env, live_key)
    time.sleep(env.get("zap_wait_sec", 3))
    return {"state": "live_tv", "channel": env.get("live_tv_channel", "default")}


def reach_epg_open(gateway, env) -> dict[str, Any]:
    """live_tv 상태에서 EPG 키로 편성표 오픈."""
    _ir(gateway, env, "EPG")
    time.sleep(2)
    return {"state": "epg_open"}


# ──────────────────────────────────────────────────────────────
# Netflix
# ──────────────────────────────────────────────────────────────

def reach_netflix_logged_in(gateway, env, credentials: dict) -> dict[str, Any]:
    """음성으로 Netflix 실행 → (필요 시) 로그인 → 프로필 선택까지.

    credentials: {"email": ..., "password": ..., "profile": ...}.
    로그인 화면 자동 입력은 STB 키보드 UI에 의존 — env["netflix_skip_login_if_session"]=true
    인 경우 세션 잔존 가정하고 키 입력만 수행.
    """
    _voice(gateway, "넷플릭스 실행", settle=5.0)

    if env.get("netflix_skip_login_if_session", True):
        # 세션 유지 가정 — 프로필 선택만 수행
        _ir(gateway, env, "OK")
        time.sleep(2.5)
        return {"state": "netflix_logged_in", "profile": credentials.get("profile")}

    # 명시적 로그인 경로 (PoC: STB on-screen keyboard 매크로는 디바이스별 학습 필요)
    # 여기선 placeholder — Sprint 2 후반 디바이스별로 implement
    raise NotImplementedError(
        "Netflix 명시적 로그인은 디바이스별 on-screen keyboard 매크로 필요. "
        "env['netflix_skip_login_if_session']=true 로 세션 유지 사용."
    )


def reach_netflix_home(gateway, env, credentials: dict) -> dict[str, Any]:
    """logged_in 이후 추가 동작 없음 — 프로필 진입 자체가 홈."""
    return {"state": "netflix_home"}


def reach_netflix_playing(gateway, env) -> dict[str, Any]:
    """Netflix 홈에서 첫 번째 추천작 재생."""
    _ir(gateway, env, "OK")  # 첫 카드
    time.sleep(2)
    _ir(gateway, env, "PLAY")
    time.sleep(env.get("playback_warmup_sec", 6))
    return {"state": "netflix_playing"}


# ──────────────────────────────────────────────────────────────
# Tving
# ──────────────────────────────────────────────────────────────

def reach_tving_logged_in(gateway, env, credentials: dict) -> dict[str, Any]:
    """음성으로 Tving 실행 → 세션 유지 가정."""
    _voice(gateway, "티빙 실행", settle=5.0)
    if env.get("tving_skip_login_if_session", True):
        _ir(gateway, env, "OK")
        time.sleep(2.5)
        return {"state": "tving_logged_in", "profile": credentials.get("profile")}
    raise NotImplementedError("Tving 명시적 로그인 매크로 미구현.")


# ──────────────────────────────────────────────────────────────
# Playback / VOD / DRM
# ──────────────────────────────────────────────────────────────

def reach_playback_active(gateway, env) -> dict[str, Any]:
    """generic VOD 재생 — STB 내장 VOD 또는 테스트용 콘텐츠.

    env['playback_source']로 분기:
      - 'live_tv': 라이브 채널 재생을 playback로 간주
      - 'vod_test_clip': 사전 등록된 테스트 클립 (env['vod_test_voice'] 발화)
    """
    source = env.get("playback_source", "vod_test_clip")
    if source == "live_tv":
        return reach_live_tv(gateway, env)

    utterance = env.get("vod_test_voice", "테스트 클립 재생")
    _voice(gateway, utterance, settle=5.0)
    time.sleep(env.get("playback_warmup_sec", 5))
    return {"state": "playback_active", "source": source}


def reach_vod_playing(gateway, env) -> dict[str, Any]:
    """playback_active 의 alias — Sprint 1 카탈로그가 두 이름을 모두 사용."""
    return reach_playback_active(gateway, env)


def reach_drm_content_playing(gateway, env) -> dict[str, Any]:
    """DRM 보호 콘텐츠 재생 — env['drm_test_voice'] 사용."""
    utterance = env.get("drm_test_voice", "넷플릭스에서 4K 콘텐츠 재생")
    _voice(gateway, utterance, settle=6.0)
    time.sleep(env.get("playback_warmup_sec", 6))
    return {"state": "drm_content_playing"}


# ──────────────────────────────────────────────────────────────
# 환경 검증 (매크로 아님 — 사전 조건 확인)
# ──────────────────────────────────────────────────────────────

def assert_hdcp_unsupported_display(env) -> dict[str, Any]:
    """HDCP 미지원 디스플레이가 라인에 연결되어 있는지 env 플래그로 확인."""
    if not env.get("hdcp_unsupported_present", False):
        return {"state": "hdcp_unsupported_display", "available": False}
    return {"state": "hdcp_unsupported_display", "available": True}
