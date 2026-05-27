"""navgraph — graph / pathfind 단위 테스트 (내장 state_map + 합성 그래프)."""
from __future__ import annotations

import pytest

from tools.navgraph.graph import Edge, StateGraph, load_graph
from tools.navgraph.pathfind import (
    Unreachable,
    bfs_path,
    navigate_steps,
    required_credentials,
)


def _g() -> StateGraph:
    nodes = {"home", "a", "b", "c", "locked"}
    edges = [
        Edge("home", "a", {"type": "ir", "key": "A"}),
        Edge("a", "b", {"type": "ir", "key": "B"}),
        Edge("home", "c", {"type": "voice", "utterance": "go c"}),
        Edge("b", "c", {"type": "ir", "key": "C"}),
        Edge("home", "locked", {"type": "ir", "key": "OK"}, requires=("pin",)),
    ]
    return StateGraph(root="home", nodes=nodes, edges=edges)


# ──────────────── graph ────────────────

def test_edge_to_step_ir():
    assert Edge("x", "y", {"type": "ir", "key": "EPG"}).to_step() == {"action": "ir", "key": "EPG"}


def test_edge_to_step_ir_repeat():
    e = Edge("x", "y", {"type": "ir", "key": "RIGHT", "repeat": 7})
    assert e.to_step() == {"action": "ir", "key": "RIGHT", "repeat": 7}


def test_edge_to_step_voice_and_wait():
    assert Edge("x", "y", {"type": "voice", "utterance": "u"}).to_step() == {"action": "voice", "utterance": "u"}
    assert Edge("x", "y", {"type": "wait", "sec": 3}).to_step() == {"action": "wait", "sec": 3}


def test_edge_to_step_unknown_raises():
    with pytest.raises(ValueError):
        Edge("x", "y", {"type": "telepathy"}).to_step()


def test_neighbors_and_reachable():
    g = _g()
    assert {e.dst for e in g.neighbors("home")} == {"a", "c", "locked"}
    assert g.reachable_from("home") == {"home", "a", "b", "c", "locked"}


def test_validate_clean():
    assert _g().validate() == []


def test_validate_detects_unreachable():
    g = StateGraph(root="home", nodes={"home", "island"},
                   edges=[Edge("home", "home", {"type": "ir", "key": "X"})])
    problems = g.validate()
    assert any("unreachable" in p for p in problems)


def test_validate_detects_bad_edge():
    g = StateGraph(root="home", nodes={"home", "a"},
                   edges=[Edge("home", "ghost", {"type": "ir", "key": "X"})])
    assert any("dst unknown" in p for p in g.validate())


# ──────────────── pathfind ────────────────

def test_bfs_same_state_empty():
    assert bfs_path(_g(), "home", "home") == []


def test_bfs_shortest_path():
    # home → c: 직접 voice 1-hop이 home→a→b→c(3-hop)보다 짧음
    path = bfs_path(_g(), "home", "c")
    assert len(path) == 1
    assert path[0].action["type"] == "voice"


def test_bfs_multi_hop():
    path = bfs_path(_g(), "home", "b")
    assert [e.dst for e in path] == ["a", "b"]


def test_bfs_requires_gate_blocks():
    with pytest.raises(Unreachable):
        bfs_path(_g(), "home", "locked")


def test_bfs_requires_gate_opens_with_available():
    path = bfs_path(_g(), "home", "locked", available={"pin"})
    assert [e.dst for e in path] == ["locked"]


def test_bfs_unknown_state_raises():
    with pytest.raises(ValueError):
        bfs_path(_g(), "home", "nope")


def test_navigate_steps_format():
    steps = navigate_steps(_g(), "b")
    assert steps == [{"action": "ir", "key": "A"}, {"action": "ir", "key": "B"}]


def test_required_credentials():
    assert required_credentials(_g(), "locked") == {"pin"}
    assert required_credentials(_g(), "b") == set()


# ──────────────── 내장 state_map.json ────────────────

def test_builtin_graph_valid():
    assert load_graph().validate() == []


def test_builtin_home_to_epg():
    steps = navigate_steps(load_graph(), "epg_open")
    keys = [s.get("key") for s in steps if s["action"] == "ir"]
    assert keys == ["LIVE", "EPG"]


def test_builtin_drm_needs_netflix_creds():
    g = load_graph()
    with pytest.raises(Unreachable):
        bfs_path(g, "home_screen", "drm_content_playing")
    steps = navigate_steps(g, "drm_content_playing", available={"netflix_credentials"})
    assert len(steps) == 3


def test_builtin_all_states_reachable_with_all_creds():
    g = load_graph()
    creds = {"netflix_credentials", "tving_credentials", "pin"}
    for node in g.nodes:
        # root 자신 제외, 모든 노드가 자격 충족 시 도달 가능해야
        navigate_steps(g, node, available=creds)  # raise 안 하면 통과
