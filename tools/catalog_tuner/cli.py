"""catalog_tuner CLI — lint / export-review / apply.

예:
  # 1) 튜닝 대상 검출
  python -m tools.catalog_tuner.cli lint

  # 2) SME 검토 워크북 (CSV)
  python -m tools.catalog_tuner.cli export-review --out review/catalog-review.csv

  # 3) overrides 적용 (key_remap + scenario_patches) — dry-run 먼저
  python -m tools.catalog_tuner.cli apply --overrides tools/catalog_tuner/overrides.json --dry-run
  python -m tools.catalog_tuner.cli apply --overrides tools/catalog_tuner/overrides.json
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from .lint import lint_catalog, summarize
from .overrides import apply_overrides
from .vocab import load_known_keys, load_known_preconditions, load_known_states

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = REPO_ROOT / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"
DEFAULT_OVERRIDES = Path(__file__).with_name("overrides.json")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _lint(catalog: list[dict]):
    return lint_catalog(
        catalog,
        known_keys=load_known_keys(),
        known_states=load_known_states(),
        known_preconditions=load_known_preconditions(),
    )


def cmd_lint(args) -> int:
    catalog = _load(Path(args.catalog))
    issues = _lint(catalog)
    summary = summarize(issues)
    print(f"🔎 lint: {len(issues)} issue / {len(catalog)} scenario")
    for kind, n in sorted(summary.items()):
        print(f"  {kind}: {n}")
    for i in issues:
        sug = f"  → 제안: {i.suggestion}" if i.suggestion else ""
        print(f"  [{i.kind}] {i.scenario_id}: '{i.detail}'{sug}")
    if args.json:
        print(json.dumps([i.to_dict() for i in issues], ensure_ascii=False, indent=2))
    # lint 이슈가 있으면 non-zero (CI 게이트용)
    return 1 if issues and args.strict else 0


def cmd_export_review(args) -> int:
    catalog = _load(Path(args.catalog))
    issues_by_id: dict[str, list] = {}
    for i in _lint(catalog):
        issues_by_id.setdefault(i.scenario_id, []).append(f"{i.kind}:{i.detail}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "priority", "preconditions", "steps", "expected",
                    "sla_ms", "lint_issues", "SME_검토의견", "SME_교정키/스텝"])
        for s in catalog:
            steps = " | ".join(
                (st.get("key") or st.get("utterance") or st.get("path") or f"{st['action']}{st.get('sec','')}")
                for st in s["steps"]
            )
            w.writerow([
                s["id"], s["category"], s["priority"],
                ",".join(s.get("preconditions", [])),
                steps, s.get("expected", ""), s.get("sla_ms", ""),
                "; ".join(issues_by_id.get(s["id"], [])), "", "",
            ])
    print(f"📝 SME 검토 워크북 → {out} ({len(catalog)} rows)")
    return 0


def cmd_apply(args) -> int:
    catalog_path = Path(args.catalog)
    catalog = _load(catalog_path)
    overrides = _load(Path(args.overrides))

    patched, log = apply_overrides(catalog, overrides)
    print(f"🔧 key_remap {log.to_dict()['key_remap_count']}건 / scenario_patch {log.to_dict()['patched_count']}건")
    for r in log.key_remaps:
        print(f"  remap: {r}")
    for p in log.patched_scenarios:
        print(f"  patch: {p}")
    if log.missing_patch_targets:
        print(f"  ⚠️ 카탈로그에 없는 patch 대상: {log.missing_patch_targets}", file=sys.stderr)

    # 적용 후 lint 재확인
    after = _lint(patched)
    print(f"🔎 적용 후 lint: {len(after)} issue (이전 {len(_lint(catalog))})")

    if args.dry_run:
        print("🟡 dry-run — 저장하지 않음")
        return 0

    # 백업 후 저장
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    backup = catalog_path.with_suffix(f".json.{ts}.bak")
    shutil.copy2(catalog_path, backup)
    catalog_path.write_text(json.dumps(patched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 백업: {backup.name}\n📝 저장: {catalog_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="catalog_tuner", description="시나리오 steps/키 사내 펌웨어 튜닝")
    ap.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    sub = ap.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("lint", help="비표준 키/네비/precondition 검출")
    pl.add_argument("--json", action="store_true")
    pl.add_argument("--strict", action="store_true", help="이슈 있으면 exit 1 (CI 게이트)")
    pl.set_defaults(func=cmd_lint)

    pe = sub.add_parser("export-review", help="SME 검토 워크북 CSV 출력")
    pe.add_argument("--out", default="review/catalog-review.csv")
    pe.set_defaults(func=cmd_export_review)

    pa = sub.add_parser("apply", help="overrides.json 적용")
    pa.add_argument("--overrides", default=str(DEFAULT_OVERRIDES))
    pa.add_argument("--dry-run", action="store_true")
    pa.set_defaults(func=cmd_apply)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
