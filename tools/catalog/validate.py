"""카탈로그 schema validation CLI.

CI 및 PR 게이트에서 호출:
  python -m tools.catalog.validate <catalog.json>

종료 코드:
  0 — 모든 시나리오가 v2 스키마 통과
  1 — 1개 이상 실패
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.catalog.schema import Scenario
else:
    from .schema import Scenario


def validate(path: Path) -> int:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print(f"❌ catalog must be JSON array, got {type(raw).__name__}", file=sys.stderr)
        return 1

    errors = 0
    seen_ids: set[str] = set()
    for i, item in enumerate(raw):
        try:
            s = Scenario.model_validate(item)
            if s.id in seen_ids:
                print(f"❌ duplicate id at index {i}: {s.id}", file=sys.stderr)
                errors += 1
            seen_ids.add(s.id)
        except Exception as e:
            sid = item.get("id", f"<index {i}>")
            print(f"❌ {sid}: {e}", file=sys.stderr)
            errors += 1

    total = len(raw)
    if errors:
        print(f"\n{errors}/{total} scenarios FAILED validation", file=sys.stderr)
        return 1
    print(f"✅ {total}/{total} scenarios passed v2 schema validation")
    return 0


def main():
    if len(sys.argv) != 2:
        print("usage: python -m tools.catalog.validate <catalog.json>", file=sys.stderr)
        sys.exit(2)
    sys.exit(validate(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
