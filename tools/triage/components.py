"""STB 실패 컴포넌트 택소노미 + 룰 키워드 + 카테고리 힌트.

LogSage 적용: UART 로그 + vision 묘사에서 컴포넌트(영상/오디오/UI/네트워크 등) 라벨링.
"""
from __future__ import annotations

# 트리아지 컴포넌트 (JIRA 라우팅 단위)
COMPONENTS = [
    "video",
    "audio",
    "ui-responsiveness",
    "network",
    "drm",
    "input-ir",
    "input-bt",
    "voice",
    "system",
    "unknown",
]

# UART 로그 / vision 묘사에서 찾는 키워드 → 컴포넌트
RULE_KEYWORDS: dict[str, list[str]] = {
    "video": [
        "vdec", "decoder", "frame drop", "framedrop", "hdmi", "resolution",
        "render", "vsync", "blank screen", "black screen", "no video", "vpu",
        "macroblock", "artifact", "freeze",
    ],
    "audio": [
        "adec", "audio", "pcm", "spdif", "mute", "avsync", "a/v sync",
        "lip sync", "no sound", "audio dropout",
    ],
    "network": [
        "dhcp", "dns", "timeout", "econnrefused", "etimedout", "socket",
        "rtsp", "cdn", "rebuffer", "buffering", "http 5", "connection reset",
        "no route", "unreachable",
    ],
    "drm": [
        "widevine", "playready", "hdcp", "license", "cenc", "drm", "cdm",
        "secure path", "key rotation", "entitlement",
    ],
    "input-ir": [
        "ir timeout", "keyevent", "no key", "remote not", "ir rx",
    ],
    "input-bt": [
        "bluetooth", "bt pair", "pairing failed", "a2dp", "hid", "gatt",
        "le scan", "bonding",
    ],
    "voice": [
        "asr", "voice", "stt", "microphone", "wakeword", "intent",
    ],
    "ui-responsiveness": [
        "anr", "watchdog", "jank", "ui timeout", "not responding",
        "input lag", "slow render", "frame budget",
    ],
    "system": [
        "panic", "reboot", "segfault", "sigsegv", "oom", "oom-killer",
        "kernel", "watchdog reset", "assert", "core dump", "deadlock",
    ],
}

# UART 신호가 약할 때 시나리오 카테고리로 추정 (낮은 confidence)
CATEGORY_HINT: dict[str, str] = {
    "EPG": "ui-responsiveness",
    "OTT": "network",
    "DRM": "drm",
    "TrickPlay": "video",
    "Search": "voice",
    "Recording": "system",
    "Parental": "ui-responsiveness",
    "Settings": "system",
    # v2.2 확장 (업데이트 53)
    "Audio": "audio",
    "Bluetooth": "input-bt",
    "Network": "network",
    "Power": "system",
    "Display": "video",
    "Voice": "voice",
    "AI": "video",          # AI 화질/음성/자막은 영상/음성 컴포넌트로
    "RCU": "input-ir",
    "Firmware": "system",
    "Home": "ui-responsiveness",
}

# 컴포넌트별 기본 심각도 (집계 JIRA severity 산정 기준)
COMPONENT_SEVERITY: dict[str, str] = {
    "system": "P1",
    "drm": "P1",
    "video": "P1",
    "audio": "P2",
    "network": "P2",
    "voice": "P2",
    "input-ir": "P2",
    "input-bt": "P3",
    "ui-responsiveness": "P3",
    "unknown": "P3",
}


def category_from_scenario_id(scenario_id: str) -> str | None:
    """scenario_id 접두사로 카테고리 추정 (카탈로그 없을 때 폴백)."""
    prefix_map = {
        "epg_": "EPG", "ott_": "OTT", "drm_": "DRM", "trickplay_": "TrickPlay",
        "search_": "Search", "recording_": "Recording",
        "parental_": "Parental", "settings_": "Settings",
        "channel_": "EPG", "voice_": "Voice", "bt_": "Bluetooth",
        # v2.2 KAON sheet prefix → 신규 카테고리
        "kaon_channel_": "EPG", "kaon_ott_": "OTT", "kaon_vod_": "OTT",
        "kaon_voice_": "Voice", "kaon_parental_": "Parental",
        "kaon_audio_": "Audio", "kaon_bt_": "Bluetooth",
        "kaon_network_": "Network", "kaon_power_": "Power",
        "kaon_boot_": "Power", "kaon_stability_": "Power",
        "kaon_display_": "Display", "kaon_rcu_": "RCU",
        "kaon_firmware_": "Firmware", "kaon_qat_": "Firmware",
        "kaon_home_": "Home", "kaon_ad_": "Home",
        "kaon_ai_": "AI",
    }
    for prefix, cat in prefix_map.items():
        if scenario_id.startswith(prefix):
            return cat
    return None
