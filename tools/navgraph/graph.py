"""StateGraph 모델 — state_map.json 로딩 + 검증 + 이웃 조회 (순수)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MAP_PATH = Path(__file__).with_name("state_map.json")


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    action: dict          # {"type": "ir"|"voice"|"wait", ...}
    requires: tuple[str, ...] = ()

    def to_step(self) -> dict:
        """catalog step 포맷으로 변환 (test_catalog _exec_step 호환)."""
        a = self.action
        t = a.get("type")
        if t == "ir":
            step = {"action": "ir", "key": a["key"]}
            if a.get("repeat"):
                step["repeat"] = a["repeat"]
            return step
        if t == "voice":
            return {"action": "voice", "utterance": a["utterance"]}
        if t == "wait":
            return {"action": "wait", "sec": a.get("sec", 1)}
        raise ValueError(f"unknown action type: {t}")


@dataclass
class StateGraph:
    root: str
    nodes: set[str]
    edges: list[Edge] = field(default_factory=list)
    _adj: dict[str, list[Edge]] = field(default_factory=dict)

    def __post_init__(self):
        self._adj = {n: [] for n in self.nodes}
        for e in self.edges:
            self._adj.setdefault(e.src, []).append(e)

    def neighbors(self, state: str) -> list[Edge]:
        return self._adj.get(state, [])

    def has_state(self, state: str) -> bool:
        return state in self.nodes

    def validate(self) -> list[str]:
        """그래프 무결성 문제 목록 반환 (빈 리스트면 정상)."""
        problems: list[str] = []
        if self.root not in self.nodes:
            problems.append(f"root '{self.root}' not in nodes")
        for e in self.edges:
            if e.src not in self.nodes:
                problems.append(f"edge src unknown: {e.src}")
            if e.dst not in self.nodes:
                problems.append(f"edge dst unknown: {e.dst}")
            if e.action.get("type") not in ("ir", "voice", "wait"):
                problems.append(f"edge {e.src}->{e.dst} bad action type")
        # root에서 도달 불가한 노드
        reachable = self.reachable_from(self.root)
        for n in self.nodes:
            if n != self.root and n not in reachable:
                problems.append(f"unreachable from root: {n}")
        return problems

    def reachable_from(self, start: str) -> set[str]:
        seen = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            for e in self.neighbors(cur):
                if e.dst not in seen:
                    seen.add(e.dst)
                    stack.append(e.dst)
        return seen


def load_graph(path: Path | None = None) -> StateGraph:
    data = json.loads((path or DEFAULT_MAP_PATH).read_text(encoding="utf-8"))
    edges = [
        Edge(src=e["from"], dst=e["to"], action=e["action"],
             requires=tuple(e.get("requires", [])))
        for e in data["edges"]
    ]
    return StateGraph(root=data["root"], nodes=set(data["nodes"]), edges=edges)
