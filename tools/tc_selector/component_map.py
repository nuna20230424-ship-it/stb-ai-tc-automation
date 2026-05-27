"""변경된 빌드 산출물(파일 경로 또는 컴포넌트명) → change_signals 번역.

빌드 시스템이 주는 정보는 보통 둘 중 하나:
  1) git diff 파일 경로 목록  → glob 매칭으로 signal 도출
  2) 컴포넌트명 목록 (이미 signal에 가까움) → 그대로 또는 alias 매핑

selector는 최종적으로 change_signals 집합만 필요로 한다.
"""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path

DEFAULT_MAP_PATH = Path(__file__).with_name("component_map.json")


def load_component_map(path: Path | None = None) -> dict[str, list[str]]:
    """component_map.json의 'map' 섹션 로딩."""
    p = path or DEFAULT_MAP_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("map", data)


def paths_to_signals(paths: list[str], component_map: dict[str, list[str]]) -> set[str]:
    """변경 파일 경로 목록을 change_signals 집합으로 변환.

    각 경로를 map의 glob 패턴과 fnmatch. 매칭되는 모든 패턴의 signal을 합집합.
    매칭 안 되는 경로는 무시(=영향 없음으로 간주, 단 unmatched는 호출측에서 추적 가능).
    """
    signals: set[str] = set()
    for raw in paths:
        path = raw.strip()
        if not path:
            continue
        for pattern, sigs in component_map.items():
            if pattern.startswith("_"):
                continue
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.rstrip("*") + "*"):
                signals.update(sigs)
    return signals


def unmatched_paths(paths: list[str], component_map: dict[str, list[str]]) -> list[str]:
    """어떤 패턴에도 매칭되지 않은 경로 — 매핑 보강이 필요한 후보."""
    out: list[str] = []
    for raw in paths:
        path = raw.strip()
        if not path:
            continue
        matched = any(
            (not pattern.startswith("_"))
            and (fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.rstrip("*") + "*"))
            for pattern in component_map
        )
        if not matched:
            out.append(path)
    return out


def components_to_signals(components: list[str], aliases: dict[str, list[str]] | None = None) -> set[str]:
    """이미 컴포넌트명으로 주어진 경우 — alias 매핑 후 signal 집합 반환.

    alias가 없으면 컴포넌트명을 그대로 signal로 취급 (소문자 정규화).
    """
    aliases = aliases or {}
    signals: set[str] = set()
    for c in components:
        c = c.strip().lower()
        if not c:
            continue
        if c in aliases:
            signals.update(aliases[c])
        else:
            signals.add(c)
    return signals
