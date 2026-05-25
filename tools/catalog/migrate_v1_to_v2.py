"""scenarios-catalog.json v1 → v2 마이그레이션.

각 시나리오에 v2 신규 8필드를 추론해서 추가하고, pydantic 모델로 검증한 뒤
사람이 읽기 쉬운 JSON 배열로 다시 쓴다.

사용:
  python -m tools.catalog.migrate_v1_to_v2 \
      --input infrastructure/notebook-gateway/data/scenarios-catalog.json \
      --output infrastructure/notebook-gateway/data/scenarios-catalog.json \
      --schema-out infrastructure/notebook-gateway/data/scenarios-catalog.schema.json

idempotent: 이미 v2 필드가 있으면 보존.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 패키지로 실행될 때와 직접 실행될 때 모두 동작하도록
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.catalog.schema import Scenario, dump_catalog, dump_json_schema, infer_defaults
else:
    from .schema import Scenario, dump_catalog, dump_json_schema, infer_defaults


def migrate(input_path: Path, output_path: Path) -> tuple[int, int]:
    """Return (total, migrated_count)."""
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"input must be JSON array, got {type(raw).__name__}")

    migrated_dicts: list[dict] = []
    migrated_count = 0
    for item in raw:
        before_keys = set(item.keys())
        merged = infer_defaults(item)
        after_keys = set(merged.keys())
        if after_keys != before_keys:
            migrated_count += 1
        migrated_dicts.append(merged)

    # 검증
    scenarios = [Scenario.model_validate(d) for d in migrated_dicts]

    dump_catalog(scenarios, output_path)
    return len(scenarios), migrated_count


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--schema-out", type=Path, default=None,
                   help="JSON Schema도 함께 저장 (옵션)")
    args = p.parse_args()

    total, migrated = migrate(args.input, args.output)
    print(f"✅ {total} scenarios processed, {migrated} migrated to v2 fields")
    print(f"   wrote {args.output}")

    if args.schema_out:
        dump_json_schema(args.schema_out)
        print(f"   wrote schema {args.schema_out}")


if __name__ == "__main__":
    main()
