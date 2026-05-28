"""파라미터 확장 엔진 — 행동 family × 데이터 axis → 구체 시나리오 (순수 함수).

family 스키마 (param_spec.json):
  {
    "id_template": "epg_zap_{slug}",
    "category": "EPG",
    "priority": "{priority}",          # axis가 priority 제공 또는 고정값
    "preconditions": ["live_tv"],
    "steps_template": [ {action..., "{ch_key}" 등 플레이스홀더 가능} ],
    "expected_template": "{name} 채널 표시",
    "expected_keywords_template": ["{name}", "채널"],
    "sla_ms": 5000,                    # 고정 또는 "{sla}"
    "change_signals": ["channel-list"],
    "axis": [ {"slug": "kbs1", "name": "KBS1", "ch_key": "CH_9", "priority": "P1"}, ... ]
  }
"""
from __future__ import annotations

import copy
import re

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _subst_str(s: str, params: dict) -> str:
    """문자열 내 {key}를 params 값으로 치환. 전체가 단일 플레이스홀더면 원타입 보존."""
    m = _PLACEHOLDER.fullmatch(s)
    if m and m.group(1) in params:
        return params[m.group(1)]          # int/str 등 원타입 그대로
    return _PLACEHOLDER.sub(lambda mo: str(params.get(mo.group(1), mo.group(0))), s)


def _subst(obj, params: dict):
    """dict/list/str 재귀 치환."""
    if isinstance(obj, str):
        return _subst_str(obj, params)
    if isinstance(obj, list):
        return [_subst(x, params) for x in obj]
    if isinstance(obj, dict):
        return {k: _subst(v, params) for k, v in obj.items()}
    return obj


def expand_family(family: dict) -> list[dict]:
    """family의 axis 각 항목으로 구체 시나리오 dict 리스트 생성."""
    axis = family.get("axis", [{}])
    scenarios: list[dict] = []
    for item in axis:
        params = dict(item)
        scenario = {
            "id": _subst_str(family["id_template"], params),
            "category": family["category"],
            "priority": _subst_str(str(family.get("priority", "P2")), params),
            "preconditions": _subst(family.get("preconditions", []), params),
            "steps": _subst(copy.deepcopy(family["steps_template"]), params),
            "expected": _subst_str(family["expected_template"], params),
            "sla_ms": int(_subst_str(str(family.get("sla_ms", 3000)), params)),
        }
        if "expected_keywords_template" in family:
            scenario["expected_keywords"] = _subst(family["expected_keywords_template"], params)
        if "change_signals" in family:
            scenario["change_signals"] = list(family["change_signals"])
        scenarios.append(scenario)
    return scenarios


def expand_all(spec: dict) -> list[dict]:
    """param_spec 전체 → 시나리오 리스트. id 중복 시 ValueError."""
    out: list[dict] = []
    seen: set[str] = set()
    for family in spec.get("families", []):
        for sc in expand_family(family):
            sid = sc["id"]
            if sid in seen:
                raise ValueError(f"중복 생성 id: {sid}")
            seen.add(sid)
            out.append(sc)
    return out


def check_collisions(generated: list[dict], existing_ids: set[str]) -> list[str]:
    """기존 카탈로그 id와 충돌하는 생성 id 목록."""
    return [sc["id"] for sc in generated if sc["id"] in existing_ids]
