"""pytest precondition fixtures — macros.py를 의존성 체인으로 래핑.

각 fixture 이름은 catalog JSON의 preconditions 문자열과 1:1 매핑된다.
test_catalog.py가 `request.getfixturevalue(f"pre_{name}")` 형태로 동적 dispatch.

설계:
- scope='function': 매 시나리오마다 도달 매크로 재실행 (idempotent 보장).
  비싼 셋업(앱 로그인 등)은 STB의 세션 유지 기능에 위임 → 두 번째 실행은 빠르게 통과.
- 의존성: 상위 상태 fixture를 인자로 받으면 pytest가 알아서 먼저 도달.
- secrets 누락 시 pytest.skip — CI/PoC 환경에서 부분 실행 가능.
"""
from __future__ import annotations

import os

import pytest

from preconditions import macros


# ──────────────────────────────────────────────────────────────
# Credentials (secrets) — env 누락 시 해당 fixture skip
# ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def netflix_credentials() -> dict:
    email = os.getenv("NETFLIX_EMAIL")
    password = os.getenv("NETFLIX_PASSWORD")
    profile = os.getenv("NETFLIX_PROFILE", "QA")
    if not email or not password:
        pytest.skip("NETFLIX_EMAIL/NETFLIX_PASSWORD env 누락 — Netflix 시나리오 skip")
    return {"email": email, "password": password, "profile": profile}


@pytest.fixture(scope="session")
def tving_credentials() -> dict:
    user_id = os.getenv("TVING_ID")
    password = os.getenv("TVING_PASSWORD")
    profile = os.getenv("TVING_PROFILE", "QA")
    if not user_id or not password:
        pytest.skip("TVING_ID/TVING_PASSWORD env 누락 — Tving 시나리오 skip")
    return {"email": user_id, "password": password, "profile": profile}


# ──────────────────────────────────────────────────────────────
# Reach fixtures — preconditions 이름과 1:1 (pre_<name>)
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def pre_home_screen(gateway, env):
    return macros.reach_home_screen(gateway, env)


@pytest.fixture
def pre_live_tv(gateway, env, pre_home_screen):
    return macros.reach_live_tv(gateway, env)


@pytest.fixture
def pre_epg_open(gateway, env, pre_live_tv):
    return macros.reach_epg_open(gateway, env)


@pytest.fixture
def pre_netflix_logged_in(gateway, env, pre_home_screen, netflix_credentials):
    return macros.reach_netflix_logged_in(gateway, env, netflix_credentials)


@pytest.fixture
def pre_netflix_home(gateway, env, pre_netflix_logged_in, netflix_credentials):
    return macros.reach_netflix_home(gateway, env, netflix_credentials)


@pytest.fixture
def pre_netflix_playing(gateway, env, pre_netflix_home):
    return macros.reach_netflix_playing(gateway, env)


@pytest.fixture
def pre_tving_logged_in(gateway, env, pre_home_screen, tving_credentials):
    return macros.reach_tving_logged_in(gateway, env, tving_credentials)


@pytest.fixture
def pre_playback_active(gateway, env, pre_home_screen):
    return macros.reach_playback_active(gateway, env)


@pytest.fixture
def pre_vod_playing(gateway, env, pre_home_screen):
    return macros.reach_vod_playing(gateway, env)


@pytest.fixture
def pre_drm_content_playing(gateway, env, pre_netflix_home):
    return macros.reach_drm_content_playing(gateway, env)


@pytest.fixture
def pre_hdcp_unsupported_display(env):
    result = macros.assert_hdcp_unsupported_display(env)
    if not result["available"]:
        pytest.skip("HDCP 미지원 디스플레이 미연결 — env['hdcp_unsupported_present']=true 필요")
    return result


# ──────────────────────────────────────────────────────────────
# 동적 dispatch helper — test_catalog.py에서 사용
# ──────────────────────────────────────────────────────────────

KNOWN_PRECONDITIONS = {
    "home_screen", "live_tv", "epg_open",
    "netflix_logged_in", "netflix_home", "netflix_playing",
    "tving_logged_in",
    "playback_active", "vod_playing",
    "drm_content_playing", "hdcp_unsupported_display",
}


def apply_preconditions(request, preconditions: list[str]) -> dict[str, dict]:
    """카탈로그 preconditions 배열을 fixture로 변환·실행.

    알 수 없는 precondition은 pytest.skip — 카탈로그에 새 이름이 추가되면
    fixtures.py에 fixture 등록을 강제하기 위함.
    """
    results: dict[str, dict] = {}
    for name in preconditions:
        if name not in KNOWN_PRECONDITIONS:
            pytest.skip(f"미등록 precondition: {name} — fixtures.py에 추가 필요")
        results[name] = request.getfixturevalue(f"pre_{name}")
    return results
