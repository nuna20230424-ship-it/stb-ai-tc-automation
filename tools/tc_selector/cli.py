"""tc_selector CLI — select / quarantine / explain.

예시:
  # 빌드에서 변경된 컴포넌트로 선택 (4시간 예산)
  python -m tools.tc_selector select --changed-components voice-asr,epg-engine --budget-min 240

  # git diff 파일 목록으로 선택
  git diff --name-only origin/main...HEAD > /tmp/changed.txt
  python -m tools.tc_selector select --changed-paths-file /tmp/changed.txt --firmware v1.2.3

  # 전체 회귀 (빌드 정보 없음)
  python -m tools.tc_selector select --full --budget-min 240

  # 격리 대상
  python -m tools.tc_selector quarantine

  # 특정 TC가 왜 선택/제외되는지
  python -m tools.tc_selector explain --id epg_open_7day --changed-components voice-asr
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .component_map import (
    components_to_signals,
    load_component_map,
    paths_to_signals,
    unmatched_paths,
)
from .flake import quarantine_list
from .selector import explain as explain_scenario
from .selector import select

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = REPO_ROOT / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"


def _load_catalog(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_signals(args) -> set[str] | None:
    """CLI 인자에서 changed_signals 집합 도출. --full이면 None(전체 회귀)."""
    if args.full:
        return None
    signals: set[str] = set()
    if args.changed_components:
        signals |= components_to_signals(args.changed_components.split(","))
    if args.changed_paths_file:
        paths = Path(args.changed_paths_file).read_text(encoding="utf-8").splitlines()
        cmap = load_component_map(Path(args.component_map) if args.component_map else None)
        signals |= paths_to_signals(paths, cmap)
        un = unmatched_paths(paths, cmap)
        if un:
            print(f"⚠️  매핑 안 된 경로 {len(un)}건 (component_map 보강 후보): "
                  f"{un[:5]}{'…' if len(un) > 5 else ''}", file=sys.stderr)
    if not signals:
        print("변경 신호가 비어있음 — --full 로 전체 회귀하거나 --changed-* 인자 확인", file=sys.stderr)
        sys.exit(2)
    return signals


def cmd_select(args) -> int:
    catalog = _load_catalog(Path(args.catalog))
    signals = _resolve_signals(args)
    result = select(
        catalog,
        signals,
        budget_sec=args.budget_min * 60,
        firmware=args.firmware,
        exclude_quarantined=not args.include_quarantined,
        smoke_risk_min=args.smoke_risk_min,
    )
    out = result.to_dict()
    out["changed_signals"] = sorted(signals) if signals is not None else "FULL"

    # 요약 출력
    print(f"📊 선택 {out['selected_count']}개 / 영향초과 {out['deferred_count']}개 / "
          f"미영향 {len(out['skipped_not_impacted'])}개 / 격리 {len(out['quarantined'])}개")
    print(f"⏱  예상 {out['selected_sec']:.0f}s / 전체 {out['eligible_sec']:.0f}s "
          f"→ 절약 {out['savings_pct']}%  (예산 {out['budget_sec']:.0f}s)")

    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"📝 {args.out} 저장")
    if args.emit_pytest_k:
        k = result.pytest_k()
        Path(args.emit_pytest_k).write_text(k, encoding="utf-8")
        print(f"📝 pytest -k 표현식 → {args.emit_pytest_k}")
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.emit_influx:
        _emit_influx(out, firmware=args.firmware)
    return 0


def _emit_influx(out: dict, *, firmware: str | None) -> None:
    """선택 결과를 InfluxDB `tc_selection` measurement로 기록 (Grafana 대시보드용).

    influxdb-client 미설치 또는 INFLUX_TOKEN 미설정 시 조용히 skip.
    """
    import os

    token = os.getenv("INFLUX_TOKEN")
    if not token:
        print("ℹ️  INFLUX_TOKEN 없음 — 메트릭 emit skip", file=sys.stderr)
        return
    try:
        from datetime import datetime, timezone

        from influxdb_client import InfluxDBClient, Point, WritePrecision
        from influxdb_client.client.write_api import SYNCHRONOUS
    except ImportError:
        print("ℹ️  influxdb-client 미설치 — 메트릭 emit skip", file=sys.stderr)
        return

    client = InfluxDBClient(
        url=os.getenv("INFLUX_URL", "http://10.0.10.50:8086"),
        token=token,
        org=os.getenv("INFLUX_ORG", "stbqa"),
    )
    mode = "full" if out.get("changed_signals") == "FULL" else "impacted"
    point = (
        Point("tc_selection")
        .tag("mode", mode)
        .tag("firmware", firmware or "unknown")
        .field("selected_count", out["selected_count"])
        .field("deferred_count", out["deferred_count"])
        .field("skipped_count", len(out["skipped_not_impacted"]))
        .field("quarantined_count", len(out["quarantined"]))
        .field("selected_sec", float(out["selected_sec"]))
        .field("eligible_sec", float(out["eligible_sec"]))
        .field("savings_pct", float(out["savings_pct"]))
        .time(datetime.now(timezone.utc), WritePrecision.NS)
    )
    client.write_api(write_options=SYNCHRONOUS).write(
        bucket=os.getenv("INFLUX_BUCKET", "stb-metrics"),
        org=os.getenv("INFLUX_ORG", "stbqa"),
        record=point,
    )
    client.close()
    print("📈 InfluxDB tc_selection 기록 완료", file=sys.stderr)


def cmd_quarantine(args) -> int:
    catalog = _load_catalog(Path(args.catalog))
    q = quarantine_list(catalog, min_runs=args.min_runs, max_fail_rate=args.max_fail_rate)
    print(f"🚧 격리 대상 {len(q)}개 (min_runs={args.min_runs}, max_fail_rate={args.max_fail_rate})")
    for item in q:
        print(f"  - {item['id']} ({item['category']}) "
              f"runs={item['runs']} pass_rate={item['pass_rate']} flake={item['flake_score']}")
    if args.json:
        print(json.dumps(q, ensure_ascii=False, indent=2))
    return 0


def cmd_explain(args) -> int:
    catalog = _load_catalog(Path(args.catalog))
    scenario = next((s for s in catalog if s["id"] == args.id), None)
    if not scenario:
        print(f"시나리오 없음: {args.id}", file=sys.stderr)
        return 1
    signals = _resolve_signals(args)
    info = explain_scenario(scenario, signals, firmware=args.firmware)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="tc_selector", description="Smart Test Selection (Phase 3)")
    ap.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="카탈로그 경로")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _add_change_args(p):
        p.add_argument("--changed-components", help="쉼표구분 컴포넌트/시그널 (예: voice-asr,epg-engine)")
        p.add_argument("--changed-paths-file", help="변경 파일 경로 목록 파일 (git diff --name-only)")
        p.add_argument("--component-map", help="커스텀 component_map.json 경로")
        p.add_argument("--full", action="store_true", help="빌드 정보 없이 전체 회귀")
        p.add_argument("--firmware", help="대상 펌웨어 버전 (firmware_min/max 매칭)")

    ps = sub.add_parser("select", help="영향 TC 선택")
    _add_change_args(ps)
    ps.add_argument("--budget-min", type=float, default=240, help="야간 윈도우 예산(분), 기본 240")
    ps.add_argument("--smoke-risk-min", type=int, default=None,
                    help="이 risk_weight 이상은 영향 없어도 항상 포함 (예: 5)")
    ps.add_argument("--include-quarantined", action="store_true", help="격리 TC도 포함")
    ps.add_argument("--out", help="선택 결과 JSON 저장 경로")
    ps.add_argument("--emit-pytest-k", help="pytest -k 표현식 파일 저장 경로")
    ps.add_argument("--emit-influx", action="store_true",
                    help="선택 결과를 InfluxDB tc_selection measurement로 기록 (Grafana)")
    ps.add_argument("--json", action="store_true", help="결과 JSON stdout 출력")
    ps.set_defaults(func=cmd_select)

    pq = sub.add_parser("quarantine", help="flake 격리 대상 조회")
    pq.add_argument("--min-runs", type=int, default=10)
    pq.add_argument("--max-fail-rate", type=float, default=0.30)
    pq.add_argument("--json", action="store_true")
    pq.set_defaults(func=cmd_quarantine)

    pe = sub.add_parser("explain", help="단일 TC 선택 사유 설명")
    pe.add_argument("--id", required=True)
    _add_change_args(pe)
    pe.set_defaults(func=cmd_explain)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
