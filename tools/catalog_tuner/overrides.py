"""SME overrides 적용 — key_remap + scenario_patches (순수 함수).

overrides.json 스키마:
  {
    "key_remap": {"1": "CH_1", "SETTINGS": "MENU"},        # 모든 ir step의 key 전역 치환
    "scenario_patches": {                                   # 시나리오별 필드 덮어쓰기
      "drm_widevine_l1": {"steps": [...], "sla_ms": 9000}
    }
  }
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field


@dataclass
class ChangeLog:
    key_remaps: list[str] = field(default_factory=list)      # "sid: OLD→NEW (step i)"
    patched_scenarios: list[str] = field(default_factory=list)
    missing_patch_targets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key_remaps": self.key_remaps,
            "patched_scenarios": self.patched_scenarios,
            "missing_patch_targets": self.missing_patch_targets,
            "key_remap_count": len(self.key_remaps),
            "patched_count": len(self.patched_scenarios),
        }


def apply_overrides(scenarios: list[dict], overrides: dict) -> tuple[list[dict], ChangeLog]:
    """overrides를 적용한 새 시나리오 리스트 + 변경 로그 반환 (원본 불변)."""
    key_remap: dict[str, str] = overrides.get("key_remap", {})
    patches: dict[str, dict] = overrides.get("scenario_patches", {})
    log = ChangeLog()

    out: list[dict] = []
    for s in scenarios:
        s = copy.deepcopy(s)
        sid = s["id"]

        # 1) key_remap — 모든 ir step
        for i, st in enumerate(s.get("steps", [])):
            if st.get("action") == "ir" and st.get("key") in key_remap:
                old = st["key"]
                st["key"] = key_remap[old]
                log.key_remaps.append(f"{sid}: {old}→{st['key']} (step {i})")

        # 2) scenario_patches — 필드 덮어쓰기
        if sid in patches:
            for k, v in patches[sid].items():
                s[k] = copy.deepcopy(v)
            log.patched_scenarios.append(sid)

        out.append(s)

    # 패치 대상이 카탈로그에 없으면 기록
    existing_ids = {s["id"] for s in scenarios}
    for pid in patches:
        if pid not in existing_ids:
            log.missing_patch_targets.append(pid)

    return out, log
