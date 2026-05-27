"""BFS 최단 경로 탐색 + navigate 스텝 생성 (순수)."""
from __future__ import annotations

from collections import deque

from .graph import Edge, StateGraph


class Unreachable(Exception):
    """start → goal 경로가 없음."""


def bfs_path(
    graph: StateGraph,
    start: str,
    goal: str,
    *,
    available: set[str] | None = None,
) -> list[Edge]:
    """start → goal 최단 엣지 경로. available은 충족된 requires 집합(자격/크레덴셜).

    requires가 available에 없는 엣지는 건너뜀. 경로 없으면 Unreachable.
    """
    if not graph.has_state(start):
        raise ValueError(f"unknown start state: {start}")
    if not graph.has_state(goal):
        raise ValueError(f"unknown goal state: {goal}")
    if start == goal:
        return []

    available = available or set()
    prev: dict[str, tuple[str, Edge]] = {}
    q = deque([start])
    seen = {start}
    while q:
        cur = q.popleft()
        for e in graph.neighbors(cur):
            if any(r not in available for r in e.requires):
                continue
            if e.dst in seen:
                continue
            seen.add(e.dst)
            prev[e.dst] = (cur, e)
            if e.dst == goal:
                return _reconstruct(prev, start, goal)
            q.append(e.dst)
    raise Unreachable(f"no path {start} → {goal} (available={sorted(available)})")


def _reconstruct(prev: dict[str, tuple[str, Edge]], start: str, goal: str) -> list[Edge]:
    path: list[Edge] = []
    cur = goal
    while cur != start:
        p, e = prev[cur]
        path.append(e)
        cur = p
    path.reverse()
    return path


def navigate_steps(
    graph: StateGraph,
    target: str,
    *,
    start: str | None = None,
    available: set[str] | None = None,
) -> list[dict]:
    """target 상태로 가는 catalog step 리스트 생성.

    start 미지정이면 root(home_screen)에서 시작. navigate 액션의 핵심 구현.
    """
    start = start or graph.root
    edges = bfs_path(graph, start, target, available=available)
    return [e.to_step() for e in edges]


def required_credentials(graph: StateGraph, target: str, *, start: str | None = None) -> set[str]:
    """target 도달에 필요한 requires(크레덴셜 등) 집합 — 무제한 available로 경로 탐색 후 수집."""
    start = start or graph.root
    edges = bfs_path(graph, start, target, available=_all_requires(graph))
    req: set[str] = set()
    for e in edges:
        req.update(e.requires)
    return req


def _all_requires(graph: StateGraph) -> set[str]:
    out: set[str] = set()
    for e in graph.edges:
        out.update(e.requires)
    return out
