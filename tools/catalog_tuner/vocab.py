"""표준 어휘 로딩 — 키맵/상태/precondition을 단일 소스에서 가져온다.

키: tools/ir-learner/codeset.py STANDARD_KEYS (importlib로 로드 — 디렉토리에 하이픈이 있어 직접 import 불가)
상태: tools/navgraph/state_map.json nodes
precondition: navgraph 노드 + env 조건(hdcp_unsupported_display)
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_known_keys() -> set[str]:
    path = REPO_ROOT / "tools" / "ir-learner" / "codeset.py"
    spec = importlib.util.spec_from_file_location("_ir_codeset", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return set(mod.STANDARD_KEYS)


def load_known_states() -> set[str]:
    path = REPO_ROOT / "tools" / "navgraph" / "state_map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data["nodes"])


# env/하드웨어 조건 — navgraph 노드는 아니지만 유효한 precondition
EXTRA_PRECONDITIONS = {"hdcp_unsupported_display"}


def load_known_preconditions() -> set[str]:
    return load_known_states() | EXTRA_PRECONDITIONS
