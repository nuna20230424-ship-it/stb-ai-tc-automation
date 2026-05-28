"""카탈로그 steps/키 lint — 사내 펌웨어 튜닝 대상 검출 (순수 함수).

검출 항목:
  - unknown_key       : ir step의 key가 표준 키맵에 없음 (+근사 제안)
  - freetext_navigate : navigate path가 navgraph 상태가 아님 (자유텍스트)
  - unknown_precondition
  - empty_voice       : voice utterance 비어있음
  - no_capture        : capture step 없음 (검증 불가)
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field


@dataclass
class Issue:
    scenario_id: str
    kind: str           # unknown_key | freetext_navigate | unknown_precondition | empty_voice | no_capture
    detail: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {"scenario_id": self.scenario_id, "kind": self.kind,
                "detail": self.detail, "suggestion": self.suggestion}


def _suggest(value: str, known: set[str]) -> str:
    m = difflib.get_close_matches(value, known, n=1, cutoff=0.5)
    return m[0] if m else ""


def lint_scenario(
    s: dict,
    *,
    known_keys: set[str],
    known_states: set[str],
    known_preconditions: set[str],
) -> list[Issue]:
    sid = s["id"]
    issues: list[Issue] = []

    for p in s.get("preconditions", []):
        if p not in known_preconditions:
            issues.append(Issue(sid, "unknown_precondition", p, _suggest(p, known_preconditions)))

    has_capture = False
    for st in s.get("steps", []):
        action = st.get("action")
        if action == "ir":
            key = st.get("key", "")
            if key not in known_keys:
                issues.append(Issue(sid, "unknown_key", key, _suggest(key, known_keys)))
        elif action == "voice":
            if not (st.get("utterance") or "").strip():
                issues.append(Issue(sid, "empty_voice", "(빈 발화)"))
        elif action == "navigate":
            path = st.get("path", "")
            if path not in known_states:
                issues.append(Issue(sid, "freetext_navigate", path, _suggest(path, known_states)))
        elif action == "capture":
            has_capture = True

    if not has_capture:
        issues.append(Issue(sid, "no_capture", "capture step 없음 — 검증 불가"))

    return issues


def lint_catalog(
    scenarios: list[dict],
    *,
    known_keys: set[str],
    known_states: set[str],
    known_preconditions: set[str],
) -> list[Issue]:
    out: list[Issue] = []
    for s in scenarios:
        out.extend(lint_scenario(
            s, known_keys=known_keys, known_states=known_states,
            known_preconditions=known_preconditions,
        ))
    return out


def summarize(issues: list[Issue]) -> dict[str, int]:
    from collections import Counter
    return dict(Counter(i.kind for i in issues))
