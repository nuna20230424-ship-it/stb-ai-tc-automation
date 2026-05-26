"""drafts/*.json → 메인 카탈로그 안전 append.

흐름:
  1. 메인 카탈로그 로드 + v2 schema 검증 (실패 시 중단)
  2. drafts/*.json 1개 이상 로드 + 각각 v2 검증
  3. ID 충돌 검사 (메인 ↔ drafts, drafts ↔ drafts)
  4. 메인 카탈로그 자동 백업 (catalog.json.YYYY-MM-DD-HHMMSS.bak)
  5. 새 시나리오 append + (옵션) 기존 overwrite
  6. infer_defaults 적용 (tags/change_signals 자동 채움)
  7. 다시 전체 검증 → 통과 시 저장, 실패 시 백업으로 롤백

ID 충돌 처리:
  --on-conflict abort     (기본) 충돌 발견 시 중단, 변경 없음
  --on-conflict skip      충돌은 무시, 새것만 추가
  --on-conflict overwrite 새 시나리오로 메인 항목 대체

사용 예:
  python -m tools.catalog.merge \\
      --catalog infrastructure/notebook-gateway/data/scenarios-catalog.json \\
      --drafts drafts/imported.json drafts/edge-netflix.json \\
      --on-conflict abort \\
      --dry-run

  python -m tools.catalog.merge \\
      --drafts drafts/imported.json   # 메인 카탈로그 기본 경로 사용
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.catalog.schema import Scenario, dump_catalog, infer_defaults
else:
    from .schema import Scenario, dump_catalog, infer_defaults


ConflictMode = Literal["abort", "skip", "overwrite"]

DEFAULT_CATALOG = Path(
    "infrastructure/notebook-gateway/data/scenarios-catalog.json"
)


# ──────────────────────────────────────────────────────────────
# I/O 헬퍼
# ──────────────────────────────────────────────────────────────

def load_json_list(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: top-level이 배열 아님 (got {type(raw).__name__})")
    return raw


def validate_all(items: list[dict], source: str) -> list[str]:
    """v2 schema 위반을 (id, error) 리스트로 반환. 빈 리스트면 모두 OK."""
    errors: list[str] = []
    for i, item in enumerate(items):
        sid = item.get("id", f"<{source}#{i}>") if isinstance(item, dict) else f"<{source}#{i}>"
        try:
            Scenario.model_validate(item)
        except Exception as e:
            errors.append(f"{source}/{sid}: {e}")
    return errors


# ──────────────────────────────────────────────────────────────
# 머지 로직
# ──────────────────────────────────────────────────────────────

def detect_conflicts(
    main_items: list[dict], drafts: dict[str, list[dict]]
) -> tuple[dict[str, list[str]], list[str]]:
    """(메인과 충돌하는 id → [draft_source 리스트], drafts끼리 중복된 id 리스트)."""
    main_ids = {item["id"] for item in main_items if isinstance(item, dict) and "id" in item}
    main_conflicts: dict[str, list[str]] = {}
    seen_in_drafts: dict[str, str] = {}
    intra_draft_dupes: list[str] = []

    for source, items in drafts.items():
        for item in items:
            if not isinstance(item, dict) or "id" not in item:
                continue
            sid = item["id"]
            if sid in main_ids:
                main_conflicts.setdefault(sid, []).append(source)
            if sid in seen_in_drafts and seen_in_drafts[sid] != source:
                intra_draft_dupes.append(
                    f"{sid}: '{seen_in_drafts[sid]}' ↔ '{source}'"
                )
            elif sid in seen_in_drafts:
                intra_draft_dupes.append(f"{sid}: '{source}' 내부 중복")
            seen_in_drafts[sid] = source

    return main_conflicts, intra_draft_dupes


def apply_merge(
    main_items: list[dict],
    drafts: dict[str, list[dict]],
    main_conflicts: dict[str, list[str]],
    on_conflict: ConflictMode,
) -> tuple[list[dict], dict[str, int]]:
    """머지 실행. (병합된 시나리오 list, 통계 dict) 반환."""
    stats = {"added": 0, "overwritten": 0, "skipped_conflict": 0}

    # drafts에 있는 시나리오를 id로 모아두기 (overwrite 모드용)
    drafts_by_id: dict[str, dict] = {}
    drafts_order: list[str] = []  # 처음 등장 순
    for source, items in drafts.items():
        for item in items:
            if not isinstance(item, dict) or "id" not in item:
                continue
            sid = item["id"]
            if sid not in drafts_by_id:
                drafts_order.append(sid)
            drafts_by_id[sid] = item  # 같은 id가 여러 draft에 있으면 마지막 승

    out: list[dict] = []
    consumed_draft_ids: set[str] = set()

    # 메인 카탈로그 순회 — overwrite 모드는 충돌 항목을 draft 버전으로 교체
    for main_item in main_items:
        sid = main_item.get("id") if isinstance(main_item, dict) else None
        if sid in main_conflicts and on_conflict == "overwrite":
            out.append(drafts_by_id[sid])
            consumed_draft_ids.add(sid)
            stats["overwritten"] += 1
        else:
            out.append(main_item)

    # drafts에서 메인에 없는 새 시나리오 append
    for sid in drafts_order:
        if sid in consumed_draft_ids:
            continue
        if sid in main_conflicts and on_conflict == "skip":
            stats["skipped_conflict"] += 1
            continue
        # abort는 호출 전에 이미 분기되어 여기 도달하지 않음
        out.append(drafts_by_id[sid])
        stats["added"] += 1

    return out, stats


def backup_catalog(path: Path) -> Path:
    """메인 카탈로그를 timestamp suffix로 복사 → 백업 경로 반환."""
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    backup = path.with_suffix(path.suffix + f".{ts}.bak")
    shutil.copy2(path, backup)
    return backup


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog="catalog-merge",
        description="drafts/*.json → 메인 카탈로그 안전 append",
    )
    p.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help=f"메인 카탈로그 경로 (기본: {DEFAULT_CATALOG})",
    )
    p.add_argument(
        "--drafts",
        nargs="+",
        required=True,
        type=Path,
        help="병합할 draft JSON 파일 1개 이상 (shell glob 가능)",
    )
    p.add_argument(
        "--on-conflict",
        choices=["abort", "skip", "overwrite"],
        default="abort",
        help="ID 충돌 처리 (기본 abort)",
    )
    p.add_argument(
        "--no-backup",
        action="store_true",
        help="자동 백업 비활성화 (권장 X)",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="실제 저장 없이 결과만 출력")

    args = p.parse_args()

    # 1. 메인 카탈로그 로드 + 검증
    if not args.catalog.exists():
        print(f"❌ 메인 카탈로그 없음: {args.catalog}", file=sys.stderr)
        return 2
    main_items = load_json_list(args.catalog)
    main_errors = validate_all(main_items, "main")
    if main_errors:
        print(f"❌ 메인 카탈로그 검증 실패 ({len(main_errors)}개):", file=sys.stderr)
        for e in main_errors:
            print(f"   - {e}", file=sys.stderr)
        print("\n메인 카탈로그를 먼저 고치고 재실행하세요.", file=sys.stderr)
        return 2

    # 2. drafts 로드 + 검증
    drafts: dict[str, list[dict]] = {}
    all_draft_errors: list[str] = []
    for draft_path in args.drafts:
        if not draft_path.exists():
            print(f"⚠️  draft 누락 skip: {draft_path}", file=sys.stderr)
            continue
        items = load_json_list(draft_path)
        errors = validate_all(items, draft_path.name)
        all_draft_errors.extend(errors)
        drafts[str(draft_path)] = items

    if all_draft_errors:
        print(f"❌ draft 검증 실패 ({len(all_draft_errors)}개):", file=sys.stderr)
        for e in all_draft_errors:
            print(f"   - {e}", file=sys.stderr)
        return 2

    total_draft = sum(len(v) for v in drafts.values())
    print(f"📥 main: {len(main_items)} scenarios | drafts: {total_draft} from {len(drafts)} files")

    # 3. 충돌 검사
    main_conflicts, intra_dupes = detect_conflicts(main_items, drafts)
    if intra_dupes:
        print(f"❌ drafts 사이 ID 중복 ({len(intra_dupes)}개) — 머지 불가:", file=sys.stderr)
        for d in intra_dupes:
            print(f"   - {d}", file=sys.stderr)
        return 2

    if main_conflicts:
        print(f"⚠️  메인 카탈로그와 ID 충돌 {len(main_conflicts)}건:")
        for sid, sources in main_conflicts.items():
            print(f"   - {sid}  (from {', '.join(Path(s).name for s in sources)})")
        if args.on_conflict == "abort":
            print(f"\n❌ on-conflict=abort — 변경 없음. "
                  f"--on-conflict skip|overwrite 로 진행하세요.", file=sys.stderr)
            return 2

    # 4. 머지 실행
    merged, stats = apply_merge(main_items, drafts, main_conflicts, args.on_conflict)

    # 5. infer_defaults — 신규 항목의 tags/change_signals 등 자동 추론
    merged = [infer_defaults(item) for item in merged]

    # 6. 최종 검증
    final_errors = validate_all(merged, "merged")
    if final_errors:
        print(f"❌ 머지 후 검증 실패 ({len(final_errors)}개) — 저장하지 않음:", file=sys.stderr)
        for e in final_errors:
            print(f"   - {e}", file=sys.stderr)
        return 2

    # 7. 리포트
    print(f"\n✅ 머지 결과: +{stats['added']} added "
          f"/ ~{stats['overwritten']} overwritten "
          f"/ -{stats['skipped_conflict']} skipped (conflict)")
    print(f"   final: {len(merged)} scenarios (was {len(main_items)})")

    if args.dry_run:
        print("\n🟡 dry-run — 저장하지 않음")
        return 0

    # 8. 백업 + 저장
    if not args.no_backup:
        backup = backup_catalog(args.catalog)
        print(f"💾 백업: {backup.name}")

    # pydantic 모델로 다시 직렬화해 일관된 출력 형식 유지
    scenarios = [Scenario.model_validate(item) for item in merged]
    dump_catalog(scenarios, args.catalog)
    print(f"📝 저장: {args.catalog}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
