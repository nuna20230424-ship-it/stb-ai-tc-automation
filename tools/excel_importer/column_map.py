"""Excel/CSV 컬럼명 → v2 Scenario 필드 매핑.

실제 사내 Excel을 확인 전이므로 **STB QA 업계 일반 패턴**으로 기본값 제공.
사용자는 --map config.yaml 또는 CLI override로 컬럼명만 바꾸면 됨.

매핑 카테고리:
- direct        : 그대로 복사 (id, expected, sla_ms 등)
- normalize     : 정규화 후 복사 (Category, Priority)
- llm_input     : LLM으로 자유 텍스트 → 구조화 변환 (Steps, Preconditions)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnMap:
    """Excel 컬럼명 → v2 schema 필드."""

    # ── direct map (스트링 변환만) ──────────────────────────────
    id: str = "TC ID"
    expected: str = "Expected Result"
    sla_ms: str = "SLA (ms)"
    owner: str = "Owner"
    jira_epic: str = "JIRA Epic"
    firmware_min: str = "Firmware Min"
    firmware_max: str = "Firmware Max"

    # ── normalize (값 변환) ───────────────────────────────────
    category: str = "Category"      # 예: "epg" / "EPG" → "EPG"
    priority: str = "Priority"      # 예: "1" / "P1" / "high" → "P1"

    # ── LLM 변환 입력 ─────────────────────────────────────────
    preconditions: str = "Pre-condition"   # 자유 텍스트
    steps: str = "Test Steps"              # 자유 텍스트 (1. ~ 2. ~ ~)

    # ── 컨텍스트(시나리오 자체 필드 아님, LLM 힌트용) ──────────
    title: str | None = "Test Case Name"   # LLM에 컨텍스트로만 전달
    remarks: str | None = "Remarks"         # 동일


DEFAULT_MAP = ColumnMap()


# ──────────────────────────────────────────────────────────────
# Category / Priority 정규화
# ──────────────────────────────────────────────────────────────

CATEGORY_ALIASES = {
    "epg": "EPG",
    "ott": "OTT",
    "vod": "OTT",
    "drm": "DRM",
    "trickplay": "TrickPlay",
    "trick play": "TrickPlay",
    "trick-play": "TrickPlay",
    "search": "Search",
    "recording": "Recording",
    "pvr": "Recording",
    "dvr": "Recording",
    "parental": "Parental",
    "parental control": "Parental",
    "settings": "Settings",
    "setting": "Settings",
    "system": "Settings",
    # 한국어 사내 엑셀 대분류 (KAON 등) — 가장 가까운 v2.2 enum으로 매핑
    "채널": "EPG",
    "epg/채널": "EPG",
    "ott/vod": "OTT",
    "vod": "OTT",
    "검색": "Search",
    "음성인식": "Voice",
    "녹화": "Recording",
    "자녀안심": "Parental",
    "자녀안심 설정": "Parental",
    "자녀보호": "Parental",
    "설정": "Settings",
    "시스템": "Settings",
    # v2.2 확장 카테고리 (업데이트 53) — KAON 25 시트 의미 보존
    "안정성": "Power",          # 장시간 시청/메모리/리부트
    "부팅": "Power",
    "power": "Power",
    "전원": "Power",
    "펌웨어": "Firmware",
    "펌웨어 업그레이드": "Firmware",
    "fw 업그레이드": "Firmware",
    "네트워크": "Network",
    "오디오": "Audio",
    "해상도": "Display",
    "블루투스": "Bluetooth",
    "rcu": "RCU",
    "홈": "Home",
    "홈_채널_vod설정": "Home",
    "재생 시나리오": "Home",      # First I AD
    "ai 화질 최적화": "AI",
    "ai 사운드 최적화": "AI",
    "ai 실시간 자막": "AI",
    "시력 보호 모드": "AI",
    "ai 시청 퀵모드": "AI",
    "메뉴 진입": "Home",         # 목소리 강조 시트의 대분류
    "기본 기능": "Voice",        # AI 음성 가전 제어 시트
    "ai 음성 가전 제어": "Voice",
}


def normalize_category(raw: str) -> str | None:
    """카테고리 원본 → v2 enum. 매칭 실패 시 None (LLM에게 위임)."""
    if not raw:
        return None
    key = str(raw).strip().lower()
    return CATEGORY_ALIASES.get(key)


PRIORITY_ALIASES = {
    "p1": "P1",
    "p2": "P2",
    "p3": "P3",
    "1": "P1",
    "2": "P2",
    "3": "P3",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
    "critical": "P1",
    "major": "P1",
    "minor": "P2",
    "trivial": "P3",
    # 한국어 — 사내 엑셀에서 중요도가 상/중/하 또는 높음/중간/낮음으로 표기되는 경우
    "상": "P1",
    "중": "P2",
    "하": "P3",
    "높음": "P1",
    "중간": "P2",
    "낮음": "P3",
    "긴급": "P1",
    "보통": "P2",
}


def normalize_priority(raw: str) -> str | None:
    if not raw:
        return None
    return PRIORITY_ALIASES.get(str(raw).strip().lower())


# ──────────────────────────────────────────────────────────────
# id slug 정규화
# ──────────────────────────────────────────────────────────────

import re as _re

_ID_NORMALIZE_RE = _re.compile(r"[^a-z0-9_]+")


def normalize_id(raw: str, category: str | None = None) -> str:
    """TC ID 원본 → v2 id (lowercase + underscore).

    예: "KAON-EPG-001" → "kaon_epg_001"
        "TC#42 (Search)" → "tc_42_search"
    """
    s = str(raw).strip().lower()
    s = _ID_NORMALIZE_RE.sub("_", s)
    s = _re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "tc_unknown"
    return s
