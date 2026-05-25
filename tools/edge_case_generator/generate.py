"""Edge-case generator CLI.

사용:
  # 기존 시나리오 1개에 대한 엣지케이스 5종
  python -m tools.edge_case_generator.generate \\
      --from-scenario ott_netflix_launch \\
      --catalog infrastructure/notebook-gateway/data/scenarios-catalog.json \\
      --output drafts/edge-netflix.json

  # 카테고리 전체에 대한 엣지케이스
  python -m tools.edge_case_generator.generate \\
      --category Recording \\
      --output drafts/edge-recording.json

  # 특정 엣지 카테고리만 (기본: 5종 전체)
  python -m tools.edge_case_generator.generate \\
      --category OTT \\
      --edge-categories negative boundary \\
      --output drafts/edge-ott-neg-bnd.json

  # Prompt-only (API 없이 LLM 프롬프트만 stdout)
  python -m tools.edge_case_generator.generate \\
      --category EPG --prompt-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.edge_case_generator.prompt import SYSTEM_PROMPT, build_user_prompt
    from tools.scenario_drafter._llm import (
        call_claude,
        extract_json,
        format_usage,
        validate_scenarios,
    )
else:
    from ..scenario_drafter._llm import (
        call_claude,
        extract_json,
        format_usage,
        validate_scenarios,
    )
    from .prompt import SYSTEM_PROMPT, build_user_prompt


EDGE_CATEGORIES = ["negative", "boundary", "stress", "accessibility", "localization"]


def find_scenario(catalog_path: Path, scenario_id: str) -> dict | None:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    for s in data:
        if s.get("id") == scenario_id:
            return s
    return None


def main():
    p = argparse.ArgumentParser(
        prog="edge-case-generator",
        description="고객관점 사용성 엣지케이스 자동 생성 (타사 인증 표준 컨텍스트)",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-scenario", help="기존 시나리오 ID (카탈로그에서 조회)")
    src.add_argument("--category",
                     choices=["EPG", "OTT", "DRM", "TrickPlay",
                              "Search", "Recording", "Parental", "Settings"])

    p.add_argument(
        "--catalog",
        type=Path,
        default=Path("infrastructure/notebook-gateway/data/scenarios-catalog.json"),
        help="기존 시나리오 조회용 카탈로그 경로",
    )
    p.add_argument("--output", type=Path, help="출력 JSON")
    p.add_argument(
        "--edge-categories",
        nargs="+",
        choices=EDGE_CATEGORIES,
        default=EDGE_CATEGORIES,
        help="생성할 엣지 카테고리 (기본 5종 전체)",
    )
    p.add_argument(
        "--count-per-category",
        type=int,
        default=2,
        help="엣지 카테고리당 시나리오 수 (기본 2)",
    )
    p.add_argument("--prompt-only", action="store_true",
                   help="API 호출 없이 system + user 프롬프트만 stdout")
    args = p.parse_args()

    base_scenario = None
    if args.from_scenario:
        base_scenario = find_scenario(args.catalog, args.from_scenario)
        if not base_scenario:
            print(f"❌ 시나리오 '{args.from_scenario}' 카탈로그에서 못 찾음",
                  file=sys.stderr)
            return 1
        category_for_log = base_scenario["category"]
    else:
        category_for_log = args.category

    user_prompt = build_user_prompt(
        category=args.category,
        base_scenario=base_scenario,
        edge_categories=args.edge_categories,
        count_per_category=args.count_per_category,
    )

    if args.prompt_only:
        print("=" * 60)
        print("# SYSTEM PROMPT")
        print("=" * 60)
        print(SYSTEM_PROMPT)
        print()
        print("=" * 60)
        print("# USER PROMPT")
        print("=" * 60)
        print(user_prompt)
        return 0

    if not args.output:
        print("❌ API 모드는 --output 필수", file=sys.stderr)
        return 1

    print(f"🤖 edge-case 생성 → {category_for_log} "
          f"× {len(args.edge_categories)} edges × ~{args.count_per_category}")
    try:
        text, usage = call_claude(SYSTEM_PROMPT, user_prompt)
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    try:
        items = json.loads(extract_json(text))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"❌ JSON 추출 실패: {e}", file=sys.stderr)
        print(f"\n원본:\n{text}", file=sys.stderr)
        return 3

    if not isinstance(items, list):
        print(f"❌ top-level이 배열 아님", file=sys.stderr)
        return 3

    ok, errors = validate_scenarios(items)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(ok, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"✅ {len(ok)}/{len(items)} edge-case scenarios v2 통과 → {args.output}")
    if errors:
        print(f"⚠️  {len(errors)} 검증 실패:", file=sys.stderr)
        for err in errors:
            print(f"   - {err}", file=sys.stderr)
    print(f"\n📊 usage: {format_usage(usage)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
