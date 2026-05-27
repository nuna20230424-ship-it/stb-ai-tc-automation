"""triage CLI — 야간 회귀 실패 evidence를 클러스터링하고 동일 라벨 1 JIRA로 집계.

배치 실행 (e2e-nightly 이후, 회귀 러너에서):
  python -m tools.triage run --evidence-dir evidence/ \
    --catalog infrastructure/notebook-gateway/data/scenarios-catalog.json \
    --use-llm --emit-jira --emit-influx --out triage-report.json

JIRA 생성은 기존 report-mcp /incident 재사용 (클러스터당 1회).
LLM 2차 라벨링은 Ollama 호환 /api/generate (OLLAMA_URL).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .cluster import cluster_failures, compression_ratio
from .labeler import label
from .signature import discover_bundles, extract_signature, load_bundle

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = REPO_ROOT / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"


def _make_llm_fn():
    """Ollama 호환 /api/generate 호출 함수 반환 (httpx 미설치/URL 없으면 None)."""
    url = os.getenv("OLLAMA_URL")
    model = os.getenv("TRIAGE_LLM_MODEL", "llama3.1")
    if not url:
        print("ℹ️  OLLAMA_URL 없음 — LLM 라벨링 비활성, 룰만 사용", file=sys.stderr)
        return None
    try:
        import httpx
    except ImportError:
        print("ℹ️  httpx 미설치 — LLM 비활성", file=sys.stderr)
        return None

    def _fn(prompt: str) -> str:
        r = httpx.post(f"{url}/api/generate",
                       json={"model": model, "prompt": prompt, "stream": False},
                       timeout=60)
        r.raise_for_status()
        return r.json().get("response", "")

    return _fn


def _load_catalog_by_id(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {s["id"]: s for s in data}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _build_jira_description(cluster: dict) -> str:
    members = "\n".join(f"  - {m}" for m in cluster["members"])
    tokens = "\n".join(f"  - {t}" for t in cluster["representative_tokens"]) or "  (UART 없음)"
    past = ", ".join(cluster["baseline_vector_ids"]) or "(없음)"
    return (
        f"*컴포넌트*: {cluster['component']}\n"
        f"*영향 시나리오* ({cluster['count']}건):\n{members}\n\n"
        f"*대표 오류 토큰*:\n{tokens}\n\n"
        f"*추정 원인*: {cluster['representative_root_cause'] or '(룰 기반 — LLM 미사용)'}\n"
        f"*펌웨어*: {', '.join(cluster['firmwares'])}\n"
        f"*라벨 출처*: {', '.join(cluster['label_sources'])} (max conf {cluster['max_confidence']})\n"
        f"*과거 동일 실패 baseline_vector_id*: {past}\n"
        f"*evidence*: {'; '.join(cluster['bundle_dirs'][:5])}"
    )


def _emit_jira(clusters: list[dict]) -> list[dict]:
    """클러스터당 report-mcp /incident 1회 호출."""
    import httpx
    report_url = os.getenv("REPORT_MCP_URL", "http://10.0.10.50:8104")
    created = []
    for c in clusters:
        payload = {
            "scenario": f"triage:{c['component']}",
            "severity": c["severity"],
            "summary": f"[triage:{c['component']}] {c['count']}건 묶음 — {c['key']}",
            "description": _build_jira_description(c),
            "evidence_url": c["bundle_dirs"][0] if c["bundle_dirs"] else None,
        }
        try:
            r = httpx.post(f"{report_url}/incident", json=payload, timeout=15)
            r.raise_for_status()
            created.append({"cluster": c["key"], **r.json()})
        except Exception as e:
            created.append({"cluster": c["key"], "error": str(e)})
    return created


def _emit_influx(clusters: list[dict], num_failures: int) -> None:
    token = os.getenv("INFLUX_TOKEN")
    if not token:
        print("ℹ️  INFLUX_TOKEN 없음 — 메트릭 emit skip", file=sys.stderr)
        return
    try:
        from datetime import datetime, timezone

        from influxdb_client import InfluxDBClient, Point, WritePrecision
        from influxdb_client.client.write_api import SYNCHRONOUS
    except ImportError:
        print("ℹ️  influxdb-client 미설치 — emit skip", file=sys.stderr)
        return
    client = InfluxDBClient(url=os.getenv("INFLUX_URL", "http://10.0.10.50:8086"),
                            token=token, org=os.getenv("INFLUX_ORG", "stbqa"))
    wa = client.write_api(write_options=SYNCHRONOUS)
    bucket = os.getenv("INFLUX_BUCKET", "stb-metrics")
    org = os.getenv("INFLUX_ORG", "stbqa")
    now = datetime.now(timezone.utc)
    # 컴포넌트별 클러스터 크기
    for c in clusters:
        wa.write(bucket=bucket, org=org, record=(
            Point("triage_cluster").tag("component", c["component"])
            .tag("severity", c["severity"]).field("size", c["count"])
            .time(now, WritePrecision.NS)))
    # 요약
    wa.write(bucket=bucket, org=org, record=(
        Point("triage_summary")
        .field("failures", num_failures).field("clusters", len(clusters))
        .field("compression_ratio", compression_ratio(num_failures, len(clusters)))
        .time(now, WritePrecision.NS)))
    client.close()
    print("📈 InfluxDB triage 메트릭 기록 완료", file=sys.stderr)


def cmd_run(args) -> int:
    evidence_root = Path(args.evidence_dir)
    if not evidence_root.is_dir():
        print(f"evidence 디렉토리 없음: {evidence_root}", file=sys.stderr)
        return 1

    catalog_by_id = _load_catalog_by_id(Path(args.catalog))
    bundles = discover_bundles(evidence_root, only_failures=not args.include_normal)
    if not bundles:
        print("트리아지할 실패 번들 없음 — 종료")
        return 0

    llm_fn = _make_llm_fn() if args.use_llm else None

    labeled = []
    for bd in bundles:
        try:
            bundle = load_bundle(bd)
        except Exception as e:
            print(f"⚠️  번들 로딩 실패 {bd.name}: {e}", file=sys.stderr)
            continue
        sig = extract_signature(bundle, bundle_dir=str(bd), catalog_by_id=catalog_by_id)
        lbl = label(sig, llm_fn=llm_fn)
        labeled.append((sig, lbl))

    clusters = cluster_failures(labeled)
    cluster_dicts = [c.to_dict() for c in clusters]
    num_failures = len(labeled)

    # 요약 출력
    cr = compression_ratio(num_failures, len(clusters))
    print(f"🧩 실패 {num_failures}건 → 클러스터 {len(clusters)}개 (압축 {cr*100:.0f}%)")
    for c in cluster_dicts:
        print(f"  [{c['severity']}] {c['component']:18s} ×{c['count']:<2d} {c['key']}")

    report = {
        "failures": num_failures,
        "clusters": len(clusters),
        "compression_ratio": cr,
        "detail": cluster_dicts,
    }
    if args.emit_jira:
        report["jira"] = _emit_jira(cluster_dicts)
        ok = sum(1 for j in report["jira"] if "error" not in j)
        print(f"🎫 JIRA {ok}/{len(cluster_dicts)} 이슈 생성")
    if args.emit_influx:
        _emit_influx(cluster_dicts, num_failures)
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"📝 {args.out} 저장")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="triage", description="자동 트리아지 (LogSage 패턴, Phase 4)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run", help="evidence 클러스터링 + 라벨링 + JIRA 집계")
    pr.add_argument("--evidence-dir", default="evidence", help="evidence 루트 (기본 evidence/)")
    pr.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    pr.add_argument("--use-llm", action="store_true", help="저신뢰 룰에 LLM 2차 라벨링 (OLLAMA_URL 필요)")
    pr.add_argument("--include-normal", action="store_true", help="normal 번들도 포함")
    pr.add_argument("--emit-jira", action="store_true", help="클러스터당 report-mcp로 1 JIRA 생성")
    pr.add_argument("--emit-influx", action="store_true", help="triage 메트릭 InfluxDB 기록")
    pr.add_argument("--out", help="트리아지 리포트 JSON 저장 경로")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_run)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
