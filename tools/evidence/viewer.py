"""Failure Viewer — evidence/ 디렉토리 조회 + export 메뉴 (CLI).

사용 예:
  # 최근 실패 10건 (기본)
  python -m tools.evidence.viewer list

  # 특정 시나리오만
  python -m tools.evidence.viewer list --scenario ott_netflix_launch

  # 특정 verdict만 (anomaly / fail / error / normal)
  python -m tools.evidence.viewer list --verdict anomaly --limit 5

  # 상세 보기 (디렉토리 prefix 매칭, 1개만 매치되어야 함)
  python -m tools.evidence.viewer show 2026-05-26T15-30-22

  # zip으로 export (외부 공유용 — JIRA 첨부, 슬랙 공유)
  python -m tools.evidence.viewer export 2026-05-26T15-30-22 --output /tmp/bug.zip

  # 오래된 evidence 정리 (30일 이상)
  python -m tools.evidence.viewer prune --older-than 30d
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.evidence.bundler import EVIDENCE_ROOT
else:
    from .bundler import EVIDENCE_ROOT


# 디렉토리명 패턴: <ISO timestamp>_<scenario_id>_<VERDICT>
_DIR_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})_(?P<scenario>.+)_(?P<verdict>[A-Z_]+)$"
)


def list_evidence(root: Path) -> list[dict]:
    """evidence/ 하위 디렉토리를 메타와 함께 나열."""
    if not root.exists():
        return []
    items = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        m = _DIR_RE.match(d.name)
        if not m:
            continue
        items.append({
            "path": d,
            "name": d.name,
            "timestamp": m.group("ts"),
            "scenario": m.group("scenario"),
            "verdict": m.group("verdict"),
        })
    items.sort(key=lambda i: i["timestamp"], reverse=True)
    return items


def resolve_one(root: Path, prefix: str) -> Path:
    """prefix로 시작하는 디렉토리 1개를 정확히 찾아 반환. 0/2개 이상이면 종료."""
    matches = [i for i in list_evidence(root) if i["name"].startswith(prefix)]
    if not matches:
        print(f"❌ '{prefix}' 로 시작하는 evidence 없음", file=sys.stderr)
        sys.exit(2)
    if len(matches) > 1:
        print(f"❌ 모호한 prefix '{prefix}' — {len(matches)}개 매치:", file=sys.stderr)
        for m in matches[:5]:
            print(f"   - {m['name']}", file=sys.stderr)
        sys.exit(2)
    return matches[0]["path"]


# ──────────────────────────────────────────────────────────────
# Subcommand: list
# ──────────────────────────────────────────────────────────────

def cmd_list(args, root: Path) -> int:
    items = list_evidence(root)
    if args.scenario:
        items = [i for i in items if i["scenario"] == args.scenario]
    if args.verdict:
        items = [i for i in items if i["verdict"].upper() == args.verdict.upper()]

    if not items:
        print("(no evidence)")
        return 0

    items = items[: args.limit]
    print(f"📂 {root} — 최근 {len(items)}건\n")
    fmt = "{ts:<19}  {verdict:<10}  {scenario}"
    print(fmt.format(ts="TIMESTAMP", verdict="VERDICT", scenario="SCENARIO"))
    print("-" * 70)
    for i in items:
        ts = i["timestamp"].replace("T", " ").replace("-", ":", 2)
        # 너무 길게 줄어들지 않게 위해 ts 그대로 두기
        print(fmt.format(
            ts=i["timestamp"], verdict=i["verdict"], scenario=i["scenario"]
        ))
    return 0


# ──────────────────────────────────────────────────────────────
# Subcommand: show
# ──────────────────────────────────────────────────────────────

def cmd_show(args, root: Path) -> int:
    d = resolve_one(root, args.prefix)
    meta_path = d / "scenario.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {}

    print(f"📦 {d.name}\n")
    print(f"  Scenario : {meta.get('scenario_id', '?')}")
    print(f"  Verdict  : {meta.get('verdict', '?')}")
    print(f"  Firmware : {meta.get('firmware', '?')}")
    print(f"  Started  : {meta.get('started_at', '?')}")

    sla, elapsed = meta.get("sla_ms"), meta.get("elapsed_ms")
    if sla and elapsed:
        delta = elapsed - sla
        suffix = f"({'+%dms 초과 ⚠️' % delta if delta > 0 else 'within SLA'})"
        print(f"  Timing   : {elapsed}ms / {sla}ms  {suffix}")

    print(f"\n  Expected : {meta.get('expected', '(없음)')}")
    det = meta.get("detection_result") or {}
    if det:
        print(f"\n  Detection:")
        print(f"    tier        : {det.get('tier')}")
        print(f"    best_score  : {det.get('best_score')}")
        print(f"    confidence  : {det.get('confidence')}")
        if det.get("description"):
            desc = det["description"]
            print(f"    description : {desc[:200]}{'...' if len(desc) > 200 else ''}")

    print(f"\n  파일:")
    for child in sorted(d.rglob("*")):
        if child.is_file():
            rel = child.relative_to(d)
            size = child.stat().st_size
            print(f"    {rel}  ({size:,} B)")

    print(f"\n💡 디버깅: open {d}/README.md")
    return 0


# ──────────────────────────────────────────────────────────────
# Subcommand: export
# ──────────────────────────────────────────────────────────────

def cmd_export(args, root: Path) -> int:
    d = resolve_one(root, args.prefix)
    out = Path(args.output or f"{d.name}.zip")
    if out.exists() and not args.force:
        print(f"❌ {out} 이미 존재 (--force로 덮어쓰기)", file=sys.stderr)
        return 2

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in d.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(d.parent))

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"📦 {out}  ({size_mb:.2f} MB)")
    print(f"   외부 공유용 zip 생성 완료 — JIRA 첨부 / 슬랙 업로드 가능")
    return 0


# ──────────────────────────────────────────────────────────────
# Subcommand: prune
# ──────────────────────────────────────────────────────────────

_DURATION_RE = re.compile(r"^(\d+)([dhm])$")


def parse_duration(s: str) -> timedelta:
    m = _DURATION_RE.match(s)
    if not m:
        raise ValueError(f"기간 형식 오류: {s} (예: 30d / 12h / 90m)")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(days=n) if unit == "d" else (
        timedelta(hours=n) if unit == "h" else timedelta(minutes=n)
    )


def cmd_prune(args, root: Path) -> int:
    cutoff = datetime.utcnow() - parse_duration(args.older_than)
    cutoff_ts = cutoff.strftime("%Y-%m-%dT%H-%M-%S")
    items = [i for i in list_evidence(root) if i["timestamp"] < cutoff_ts]
    if not items:
        print(f"(no evidence older than {args.older_than})")
        return 0

    print(f"⚠️  삭제 후보 {len(items)}개 (older than {args.older_than}):")
    for i in items[:10]:
        print(f"   - {i['name']}")
    if len(items) > 10:
        print(f"   ... 외 {len(items) - 10}개")

    if not args.yes:
        print("\n실제 삭제는 --yes 와 함께 재실행")
        return 0

    for i in items:
        shutil.rmtree(i["path"])
    print(f"\n✅ {len(items)}개 디렉토리 삭제 완료")
    return 0


# ──────────────────────────────────────────────────────────────
# CLI 진입
# ──────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog="failure-viewer",
        description="TC 자동화 실패 evidence 조회/추출 메뉴",
    )
    p.add_argument(
        "--root", type=Path, default=EVIDENCE_ROOT,
        help=f"evidence 디렉토리 (기본: {EVIDENCE_ROOT})",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="최근 evidence 목록")
    p_list.add_argument("--limit", type=int, default=10)
    p_list.add_argument("--scenario", help="시나리오 ID 필터")
    p_list.add_argument("--verdict", help="verdict 필터 (anomaly / fail / normal 등)")

    p_show = sub.add_parser("show", help="evidence 상세 보기")
    p_show.add_argument("prefix", help="디렉토리명 prefix (timestamp 또는 ID 일부)")

    p_export = sub.add_parser("export", help="zip으로 export (외부 공유용)")
    p_export.add_argument("prefix")
    p_export.add_argument("--output", "-o", help="출력 zip 경로 (기본 <name>.zip)")
    p_export.add_argument("--force", "-f", action="store_true",
                          help="기존 파일 덮어쓰기")

    p_prune = sub.add_parser("prune", help="오래된 evidence 삭제")
    p_prune.add_argument("--older-than", default="30d",
                         help="기간 (30d / 12h / 90m)")
    p_prune.add_argument("--yes", "-y", action="store_true",
                         help="확인 없이 즉시 삭제")

    args = p.parse_args()
    root = Path(args.root)

    if args.cmd == "list":
        sys.exit(cmd_list(args, root))
    elif args.cmd == "show":
        sys.exit(cmd_show(args, root))
    elif args.cmd == "export":
        sys.exit(cmd_export(args, root))
    elif args.cmd == "prune":
        sys.exit(cmd_prune(args, root))


if __name__ == "__main__":
    main()
