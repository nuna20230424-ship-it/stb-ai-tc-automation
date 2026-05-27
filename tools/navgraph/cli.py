"""navgraph CLI — path / validate / states / dot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .graph import load_graph
from .pathfind import Unreachable, bfs_path, navigate_steps, required_credentials


def cmd_path(args) -> int:
    graph = load_graph(Path(args.map) if args.map else None)
    available = set(args.available or [])
    try:
        steps = navigate_steps(graph, args.to, start=args.from_, available=available)
    except Unreachable as e:
        print(f"❌ {e}", file=sys.stderr)
        req = required_credentials(graph, args.to, start=args.from_)
        if req - available:
            print(f"   필요 자격: {sorted(req)} (제공: {sorted(available)})", file=sys.stderr)
        return 1
    start = args.from_ or graph.root
    print(f"🧭 {start} → {args.to} ({len(steps)} step)")
    for i, s in enumerate(steps, 1):
        print(f"  {i}. {json.dumps(s, ensure_ascii=False)}")
    if args.json:
        print(json.dumps(steps, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args) -> int:
    graph = load_graph(Path(args.map) if args.map else None)
    problems = graph.validate()
    if not problems:
        print(f"✅ 그래프 정상 — 노드 {len(graph.nodes)}, 엣지 {len(graph.edges)}")
        return 0
    print(f"❌ 문제 {len(problems)}건:")
    for p in problems:
        print(f"  - {p}")
    return 1


def cmd_states(args) -> int:
    graph = load_graph(Path(args.map) if args.map else None)
    reachable = graph.reachable_from(graph.root)
    for n in sorted(graph.nodes):
        flag = "" if n in reachable else "  ⚠️ unreachable"
        out = [e.dst for e in graph.neighbors(n)]
        print(f"  {n}{flag}  → {out}")
    return 0


def cmd_dot(args) -> int:
    """Graphviz DOT 출력 (시각화용)."""
    graph = load_graph(Path(args.map) if args.map else None)
    print("digraph stb_ui {")
    print('  rankdir=LR; node [shape=box, style=rounded];')
    print(f'  "{graph.root}" [style="rounded,filled", fillcolor=lightblue];')
    for e in graph.edges:
        a = e.action
        label = a.get("key") or a.get("utterance") or a.get("type")
        req = f"\\n[{','.join(e.requires)}]" if e.requires else ""
        print(f'  "{e.src}" -> "{e.dst}" [label="{label}{req}"];')
    print("}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="navgraph", description="STB UI 상태 그래프 내비게이션 (Phase 5)")
    ap.add_argument("--map", help="state_map.json 경로 (기본 내장)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("path", help="start → target 경로(스텝) 생성")
    pp.add_argument("--to", required=True, help="목표 상태")
    pp.add_argument("--from", dest="from_", help="시작 상태 (기본 root=home_screen)")
    pp.add_argument("--available", nargs="*", help="충족된 requires (예: netflix_credentials pin)")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_path)

    pv = sub.add_parser("validate", help="그래프 무결성 검사")
    pv.set_defaults(func=cmd_validate)

    ps = sub.add_parser("states", help="상태/엣지 목록")
    ps.set_defaults(func=cmd_states)

    pd = sub.add_parser("dot", help="Graphviz DOT 출력")
    pd.set_defaults(func=cmd_dot)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
