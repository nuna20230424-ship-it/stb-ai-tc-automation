"""console_data CLI — `python -m tools.console_data build ...`.

흐름:
  1. catalog (scenarios-catalog.json) 로드
  2. 실행 결과 로드 — InfluxDB 우선, 폴백으로 --runs-json
  3. BuildContext 구성 (firmware / credentials / deferred / mcp 상태)
  4. build_console_data() → JSON 파일로 저장

CI에서 호출 예:
    python -m tools.console_data build \\
        --catalog infrastructure/notebook-gateway/data/scenarios-catalog.json \\
        --output docs/console-data.json \\
        --firmware "$FIRMWARE" \\
        --runs-json tests/reports/runs.json \\
        --deferred-file tests/reports/deferred.json \\
        --available-credentials netflix_credentials,tving_credentials
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .builder import (
    BuildContext,
    build_console_data,
    load_runs_from_influx,
    load_runs_from_json,
)


def _parse_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {v.strip() for v in value.split(",") if v.strip()}


def _load_deferred(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {str(x) for x in data}
    if isinstance(data, dict) and "deferred" in data:
        return {str(x) for x in data["deferred"]}
    return set()


def cmd_build(args: argparse.Namespace) -> int:
    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        print(f"[console_data] catalog not found: {catalog_path}", file=sys.stderr)
        return 2
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    runs: dict[str, dict] = {}
    source = "no-runs"
    if args.influx_url and args.influx_token and args.influx_org and args.influx_bucket:
        runs = load_runs_from_influx(
            args.influx_url,
            args.influx_token,
            args.influx_org,
            args.influx_bucket,
            lookback=args.influx_lookback,
        )
        if runs:
            source = "influx"
    if not runs and args.runs_json:
        runs = load_runs_from_json(Path(args.runs_json))
        if runs:
            source = "json"

    ctx = BuildContext(
        firmware=args.firmware or "unknown",
        available_credentials=_parse_csv(args.available_credentials),
        deferred_ids=_load_deferred(Path(args.deferred_file) if args.deferred_file else None),
        mcp_unreachable=args.mcp_unreachable,
    )

    payload = build_console_data(catalog, runs, ctx)
    payload["source"] = source  # builder의 'real|no-runs' 보다 더 구체적인 라벨

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = payload["summary"]
    print(
        f"[console_data] {out} — source={source} "
        f"total={summary['total']} pass={summary['pass']} fail={summary['fail']} "
        f"nt={summary['nt']} na={summary['na']}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools.console_data", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="console-data.json 생성")
    b.add_argument(
        "--catalog",
        default="infrastructure/notebook-gateway/data/scenarios-catalog.json",
        help="시나리오 카탈로그 JSON 경로",
    )
    b.add_argument("--output", default="docs/console-data.json", help="출력 JSON 경로")
    b.add_argument("--firmware", default=os.environ.get("FIRMWARE", "unknown"))
    b.add_argument(
        "--available-credentials",
        default=os.environ.get("AVAILABLE_CREDENTIALS", ""),
        help="콤마구분 (예: netflix_credentials,tving_credentials)",
    )
    b.add_argument("--deferred-file", default=None, help="tc_selector deferred IDs JSON")
    b.add_argument("--mcp-unreachable", action="store_true")
    b.add_argument("--runs-json", default=None, help="실행 결과 JSON 폴백 (CI)")
    b.add_argument("--influx-url", default=os.environ.get("INFLUX_URL"))
    b.add_argument("--influx-token", default=os.environ.get("INFLUX_TOKEN"))
    b.add_argument("--influx-org", default=os.environ.get("INFLUX_ORG"))
    b.add_argument("--influx-bucket", default=os.environ.get("INFLUX_BUCKET"))
    b.add_argument("--influx-lookback", default="-24h")
    b.set_defaults(func=cmd_build)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
