"""drafts/*.json → 카탈로그에 안전하게 머지.

업데이트 53 — bulk import 결과를 카탈로그에 합치는 마지막 단계.

사용:
    # 머지 전 자동 백업 + dry-run 미리보기 + 실 머지
    python -m tools.excel_importer.merge_into_catalog \\
        --import-from drafts/kaon-all.json \\
        --catalog infrastructure/notebook-gateway/data/scenarios-catalog.json \\
        --backup-suffix 2026-05-30-pre-kaon

기본 정책:
- ID 충돌 시 기본 skip (`--on-conflict replace`로 덮어쓰기 가능)
- 머지 전 카탈로그를 `<catalog>.<suffix>.bak`로 백업
- pydantic 검증 — 검증 실패 항목은 머지 제외 + 보고
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.catalog.schema import Scenario


def _validate(item: dict) -> tuple[bool, str]:
    try:
        Scenario(**item)
        return True, ""
    except Exception as e:
        return False, str(e)[:120]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="merge-into-catalog",
        description="bulk import 결과 JSON을 카탈로그에 합쳐서 저장",
    )
    p.add_argument("--import-from", required=True, type=Path)
    p.add_argument("--catalog", required=True, type=Path)
    p.add_argument("--backup-suffix", default="merge",
                   help="자동 백업 파일명 suffix (기본: 'merge')")
    p.add_argument("--on-conflict", choices=["skip", "replace"], default="skip",
                   help="ID 충돌 시 정책 (기본: skip)")
    p.add_argument("--dry-run", action="store_true",
                   help="실제 저장하지 않고 미리보기만")
    args = p.parse_args(argv)

    existing = json.loads(args.catalog.read_text(encoding="utf-8"))
    new = json.loads(args.import_from.read_text(encoding="utf-8"))
    existing_by_id = {s["id"]: s for s in existing}
    new_by_id = {s["id"]: s for s in new}

    # 검증
    valid_new = []
    invalid: list[tuple[str, str]] = []
    for s in new:
        ok, msg = _validate(s)
        if ok:
            valid_new.append(s)
        else:
            invalid.append((s.get("id", "?"), msg))

    # 충돌 분류
    conflicts = [s for s in valid_new if s["id"] in existing_by_id]
    additions = [s for s in valid_new if s["id"] not in existing_by_id]

    # 결과 카탈로그 빌드
    if args.on_conflict == "replace":
        merged_by_id = dict(existing_by_id)
        for s in valid_new:
            merged_by_id[s["id"]] = s
        merged = list(merged_by_id.values())
    else:  # skip
        merged = existing + additions

    print(f"📦 머지 미리보기")
    print(f"   카탈로그:   {args.catalog} ({len(existing)}건)")
    print(f"   import:    {args.import_from} ({len(new)}건)")
    print(f"   검증 통과: {len(valid_new)}건 / 실패 {len(invalid)}건")
    print(f"   추가:      {len(additions)}건")
    print(f"   충돌:      {len(conflicts)}건 → {args.on_conflict}")
    print(f"   결과 총계: {len(merged)}건")

    if invalid:
        print(f"\n⚠️  검증 실패 (상위 5):")
        for sid, msg in invalid[:5]:
            print(f"   {sid}: {msg}")

    if args.dry_run:
        print("\n(dry-run — 저장하지 않음)")
        return 0

    backup = args.catalog.with_suffix(
        f".{args.backup_suffix}.bak" if not args.backup_suffix.startswith(".")
        else f"{args.backup_suffix}.bak"
    )
    # 더 안전한 백업명 — 카탈로그.json.<suffix>.bak
    backup = args.catalog.parent / f"{args.catalog.name}.{args.backup_suffix}.bak"
    backup.write_text(args.catalog.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"\n💾 백업: {backup}")

    args.catalog.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"✅ 머지 완료: {args.catalog}")
    return 0 if not invalid else 1


if __name__ == "__main__":
    sys.exit(main())
