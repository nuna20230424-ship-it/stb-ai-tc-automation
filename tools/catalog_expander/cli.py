"""catalog_expander CLI — generate / count.

흐름:
  1. param_spec.json → expand_all → 구체 시나리오
  2. 기존 카탈로그 id와 충돌 검사
  3. drafts JSON 저장 → tools.catalog.merge로 병합 (infer_defaults + 검증)

예:
  python -m tools.catalog_expander.cli generate \
    --spec tools/catalog_expander/param_spec.json \
    --existing infrastructure/notebook-gateway/data/scenarios-catalog.json \
    --out drafts/expanded.json
  python -m tools.catalog.merge --drafts drafts/expanded.json --on-conflict abort
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .expander import check_collisions, expand_all

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = Path(__file__).with_name("param_spec.json")
DEFAULT_CATALOG = REPO_ROOT / "infrastructure" / "notebook-gateway" / "data" / "scenarios-catalog.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_generate(args) -> int:
    spec = _load(Path(args.spec))
    generated = expand_all(spec)

    existing_ids: set[str] = set()
    if args.existing and Path(args.existing).exists():
        existing_ids = {s["id"] for s in _load(Path(args.existing))}

    collisions = check_collisions(generated, existing_ids)
    if collisions:
        print(f"❌ 기존 카탈로그와 id 충돌 {len(collisions)}건: {collisions[:10]}", file=sys.stderr)
        if not args.allow_collision:
            return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")

    by_cat = Counter(s["category"] for s in generated)
    by_pri = Counter(s["priority"] for s in generated)
    print(f"✅ 생성 {len(generated)}개 → {out}")
    print(f"   카테고리: {dict(by_cat)}")
    print(f"   우선순위: {dict(by_pri)}")
    if existing_ids:
        print(f"   기존 {len(existing_ids)} + 신규 {len(generated)} = {len(existing_ids) + len(generated)} (충돌 {len(collisions)})")
    return 0


def cmd_count(args) -> int:
    spec = _load(Path(args.spec))
    generated = expand_all(spec)
    by_cat = Counter(s["category"] for s in generated)
    print(f"생성 예정 {len(generated)}개")
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat}: {n}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="catalog_expander", description="파라미터 확장 (36→200 TC)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("generate", help="param_spec → drafts JSON")
    pg.add_argument("--spec", default=str(DEFAULT_SPEC))
    pg.add_argument("--existing", default=str(DEFAULT_CATALOG), help="충돌 검사용 기존 카탈로그")
    pg.add_argument("--out", required=True)
    pg.add_argument("--allow-collision", action="store_true")
    pg.set_defaults(func=cmd_generate)

    pc = sub.add_parser("count", help="생성 예정 수만 출력")
    pc.add_argument("--spec", default=str(DEFAULT_SPEC))
    pc.set_defaults(func=cmd_count)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
