"""Excel/CSV TC 시트 → v2 카탈로그 JSON importer.

사용:
  # API 모드 — Claude가 자유 텍스트 step/precondition을 구조화
  python -m tools.excel_importer.importer \\
      --input docs/specs/example-tc-sheet.csv \\
      --output drafts/imported.json

  # Dry-run — LLM 호출 없이 direct map만 (Steps/Precondition은 null)
  python -m tools.excel_importer.importer \\
      --input docs/specs/example-tc-sheet.csv \\
      --output drafts/direct-map-only.json \\
      --dry-run

  # 컬럼 매핑 커스텀 (사용자 Excel 컬럼명이 다를 때)
  python -m tools.excel_importer.importer \\
      --input my-tc.xlsx --output drafts/my.json \\
      --column-id "Test ID" --column-steps "Procedure"

  # batch 크기 조절 (LLM 호출당 행 수, 기본 8)
  python -m tools.excel_importer.importer ... --batch-size 5

처리 흐름:
  1. .csv / .xlsx 로드 (pandas)
  2. Direct map: id / category / priority / expected / sla_ms / owner
  3. batch_size씩 묶어 LLM 호출 → preconditions[] + steps[] 채움
  4. pydantic Scenario 검증 → 통과만 출력
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.catalog.schema import PRIORITY_TO_RISK_WEIGHT
    from tools.excel_importer.column_map import (
        ColumnMap,
        DEFAULT_MAP,
        normalize_category,
        normalize_id,
        normalize_priority,
    )
    from tools.excel_importer.prompt import SYSTEM_PROMPT, build_user_prompt
    from tools.scenario_drafter._llm import (
        call_claude,
        extract_json,
        format_usage,
        validate_scenarios,
    )
else:
    from ..catalog.schema import PRIORITY_TO_RISK_WEIGHT
    from ..scenario_drafter._llm import (
        call_claude,
        extract_json,
        format_usage,
        validate_scenarios,
    )
    from .column_map import (
        ColumnMap,
        DEFAULT_MAP,
        normalize_category,
        normalize_id,
        normalize_priority,
    )
    from .prompt import SYSTEM_PROMPT, build_user_prompt


# ──────────────────────────────────────────────────────────────
# 로딩
# ──────────────────────────────────────────────────────────────

def list_sheets(path: Path) -> list[str]:
    """엑셀 파일의 시트 이름 목록 반환 (csv는 빈 리스트)."""
    if path.suffix.lower() not in (".xlsx", ".xls"):
        return []
    try:
        import pandas as pd
    except ImportError as e:
        raise RuntimeError("pandas 미설치. `pip install pandas openpyxl` 후 재실행하세요.") from e
    return pd.ExcelFile(path).sheet_names


def _resolve_sheet(path: Path, requested: str | None) -> str | None:
    """요청 시트명을 대소문자/공백 무시로 실제 시트명에 매칭."""
    sheets = list_sheets(path)
    if not requested or not sheets:
        return None
    norm = lambda s: s.strip().replace(" ", "").lower()
    target = norm(requested)
    for s in sheets:
        if norm(s) == target:
            return s
    # 부분 매칭 시도 — "채널" 요청에 "[채널 시트]"가 있어도 매칭
    for s in sheets:
        if target in norm(s):
            return s
    raise ValueError(
        f"엑셀 파일에 시트 '{requested}' 없음. 사용 가능 시트: {sheets}"
    )


def load_rows(path: Path, sheet: str | None = None) -> list[dict]:
    """csv/xlsx → list of dict (컬럼명 → 값).

    Args:
        sheet: 엑셀일 때 특정 시트만 로드 (대소문자/공백 무시 매칭). None이면 첫 시트.
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise RuntimeError(
            "pandas 미설치. `pip install pandas openpyxl` 후 재실행하세요."
        ) from e

    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        resolved = _resolve_sheet(path, sheet) if sheet else 0
        df = pd.read_excel(path, sheet_name=resolved, dtype=str, keep_default_na=False)
    elif suffix == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    else:
        raise ValueError(f"지원하지 않는 확장자: {suffix} (.csv/.xlsx만)")
    return df.to_dict(orient="records")


# ──────────────────────────────────────────────────────────────
# Direct map — 자유 텍스트 없이 결정 가능한 필드
# ──────────────────────────────────────────────────────────────

def direct_map_row(row: dict, cmap: ColumnMap) -> dict | None:
    """row → 부분적 v2 dict (preconditions/steps는 비어있음).

    필수 필드(id/category/priority/expected/sla_ms) 미충족 시 None.
    """
    raw_id = row.get(cmap.id, "")
    raw_cat = row.get(cmap.category, "")
    raw_pri = row.get(cmap.priority, "")
    raw_exp = row.get(cmap.expected, "")
    raw_sla = row.get(cmap.sla_ms, "")

    if not raw_id or not raw_cat or not raw_pri or not raw_exp:
        return None

    cat = normalize_category(raw_cat)
    pri = normalize_priority(raw_pri)
    if not cat or not pri:
        return None

    try:
        sla = int(str(raw_sla).strip())
    except (ValueError, TypeError):
        return None
    if sla <= 0:
        return None

    return {
        "id": normalize_id(raw_id, cat),
        "category": cat,
        "priority": pri,
        "preconditions": [],   # ← LLM이 채움
        "steps": [],            # ← LLM이 채움
        "expected": str(raw_exp).strip(),
        "sla_ms": sla,
        "risk_weight": PRIORITY_TO_RISK_WEIGHT.get(pri, 2),
        "firmware_min": (row.get(cmap.firmware_min) or None) or None,
        "firmware_max": (row.get(cmap.firmware_max) or None) or None,
        "owner": (row.get(cmap.owner) or None) or None,
        "jira_epic": (row.get(cmap.jira_epic) or None) or None,
    }


# ──────────────────────────────────────────────────────────────
# LLM batch 호출 — Steps/Precondition 자유 텍스트를 구조화로
# ──────────────────────────────────────────────────────────────

def build_llm_input(rows: list[dict], partial: list[dict], cmap: ColumnMap) -> list[dict]:
    """LLM에 보낼 batch input — partial[i]이 None이면 그 row는 skip."""
    out = []
    for i, (row, p) in enumerate(zip(rows, partial)):
        if p is None:
            continue
        item = {
            "row_index": i,
            "title": row.get(cmap.title) if cmap.title else None,
            "category": p["category"],
            "precondition_raw": (row.get(cmap.preconditions) or "").strip(),
            "steps_raw": (row.get(cmap.steps) or "").strip(),
        }
        out.append(item)
    return out


def apply_llm_result(
    partial: list[dict], llm_result: list[dict]
) -> tuple[list[dict], list[str]]:
    """LLM 결과(row_index 키 포함)를 partial에 병합. (병합된 항목, 에러)."""
    errors: list[str] = []
    by_idx = {r.get("row_index"): r for r in llm_result if isinstance(r, dict)}
    merged: list[dict] = []
    for i, p in enumerate(partial):
        if p is None:
            continue
        r = by_idx.get(i)
        if not r:
            errors.append(f"row {i} ({p['id']}): LLM 응답에 row_index 누락")
            continue
        if "preconditions" not in r or "steps" not in r:
            errors.append(f"row {i} ({p['id']}): preconditions/steps 키 누락")
            continue
        merged_item = dict(p)
        merged_item["preconditions"] = r["preconditions"]
        merged_item["steps"] = r["steps"]
        merged.append(merged_item)
    return merged, errors


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog="excel-importer",
        description="Excel/CSV TC 시트 → v2 카탈로그 JSON",
    )
    p.add_argument("--input", required=True, type=Path, help="입력 .csv 또는 .xlsx")
    p.add_argument("--output", type=Path, help="출력 .json (검증 통과만). --list-sheets 시에는 불필요.")
    p.add_argument("--sheet", default="채널",
                   help="엑셀 시트 이름 (기본 '채널', 대소문자/공백 무시). csv에는 무시됨.")
    p.add_argument("--list-sheets", action="store_true",
                   help="엑셀 시트 목록만 출력하고 종료 (어떤 시트가 있는지 확인용)")
    p.add_argument("--batch-size", type=int, default=8, help="LLM 호출당 행 수")
    p.add_argument("--dry-run", action="store_true",
                   help="LLM 호출 없이 direct map만 — steps/preconditions는 빈 배열")
    p.add_argument("--prompt-only", action="store_true",
                   help="API 호출 없이 system + first batch user 프롬프트만 출력")

    # 컬럼 매핑 override
    p.add_argument("--column-id", default=DEFAULT_MAP.id)
    p.add_argument("--column-category", default=DEFAULT_MAP.category)
    p.add_argument("--column-priority", default=DEFAULT_MAP.priority)
    p.add_argument("--column-preconditions", default=DEFAULT_MAP.preconditions)
    p.add_argument("--column-steps", default=DEFAULT_MAP.steps)
    p.add_argument("--column-expected", default=DEFAULT_MAP.expected)
    p.add_argument("--column-sla", default=DEFAULT_MAP.sla_ms)
    p.add_argument("--column-owner", default=DEFAULT_MAP.owner)

    args = p.parse_args()

    # --list-sheets: 시트만 출력 후 종료 (업로드 후 시트 확인용)
    if args.list_sheets:
        sheets = list_sheets(args.input)
        if not sheets:
            print(f"⚠️  {args.input} — 엑셀이 아니거나 시트 없음", file=sys.stderr)
            return 1
        print(f"📑 {args.input} 시트 목록 ({len(sheets)}개):")
        for s in sheets:
            print(f"  - {s}")
        return 0

    if not args.output:
        print("❌ --output 필수 (--list-sheets 사용 시에만 생략 가능)", file=sys.stderr)
        return 2

    cmap = ColumnMap(
        id=args.column_id,
        category=args.column_category,
        priority=args.column_priority,
        preconditions=args.column_preconditions,
        steps=args.column_steps,
        expected=args.column_expected,
        sla_ms=args.column_sla,
        owner=args.column_owner,
    )

    rows = load_rows(args.input, sheet=args.sheet)
    sheet_label = f" (시트 '{args.sheet}')" if args.input.suffix.lower() in (".xlsx", ".xls") else ""
    print(f"📥 {len(rows)} rows loaded{sheet_label}")

    # Direct map
    partial = [direct_map_row(r, cmap) for r in rows]
    skipped = sum(1 for p in partial if p is None)
    print(f"📋 direct map: {len(rows) - skipped} 통과, {skipped} skip(필수 필드 누락)")

    if args.dry_run:
        # LLM 없이 저장
        out = [p for p in partial if p is not None]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"✅ dry-run: {len(out)} scenarios → {args.output} (steps/preconditions 빈 채로)")
        return 0

    # LLM batch input 구성
    llm_input = build_llm_input(rows, partial, cmap)
    if not llm_input:
        print("⚠️  LLM 변환 대상 없음", file=sys.stderr)
        return 1

    if args.prompt_only:
        # 첫 batch만 출력
        first_batch = llm_input[: args.batch_size]
        print("=" * 60)
        print("# SYSTEM PROMPT")
        print("=" * 60)
        print(SYSTEM_PROMPT)
        print()
        print("=" * 60)
        print(f"# USER PROMPT (첫 batch, {len(first_batch)}/{len(llm_input)} rows)")
        print("=" * 60)
        print(build_user_prompt(first_batch))
        return 0

    # 실제 LLM batch 호출
    all_merged: list[dict] = []
    all_errors: list[str] = []
    total_usage = {"input_tokens": 0, "output_tokens": 0,
                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}

    for batch_idx in range(0, len(llm_input), args.batch_size):
        batch = llm_input[batch_idx : batch_idx + args.batch_size]
        print(f"🤖 batch {batch_idx // args.batch_size + 1}: {len(batch)} rows → Claude...")
        try:
            text, usage = call_claude(SYSTEM_PROMPT, build_user_prompt(batch))
        except RuntimeError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 2
        for k in total_usage:
            total_usage[k] += usage[k]

        try:
            llm_result = json.loads(extract_json(text))
        except (ValueError, json.JSONDecodeError) as e:
            print(f"❌ batch {batch_idx}: JSON 추출 실패 — {e}", file=sys.stderr)
            all_errors.append(f"batch {batch_idx}: {e}")
            continue

        if not isinstance(llm_result, list):
            all_errors.append(f"batch {batch_idx}: top-level이 배열 아님")
            continue

        merged, errs = apply_llm_result(partial, llm_result)
        # batch에 속한 row_index만 골라서 merge
        batch_idxs = {item["row_index"] for item in batch}
        all_merged.extend(m for m in merged if any(m["id"] == partial[i]["id"]
                                                    for i in batch_idxs if partial[i]))
        all_errors.extend(errs)

    # 검증
    ok, validation_errors = validate_scenarios(all_merged)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(ok, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\n✅ {len(ok)}/{len(rows)} scenarios v2 schema 통과 → {args.output}")
    if all_errors or validation_errors:
        print(f"⚠️  LLM 변환 에러 {len(all_errors)} / 검증 실패 {len(validation_errors)}:",
              file=sys.stderr)
        for err in all_errors + validation_errors:
            print(f"   - {err}", file=sys.stderr)

    print(f"\n📊 total usage: {format_usage(total_usage)}")
    if total_usage["cache_read_input_tokens"] > 0:
        ratio = total_usage["cache_read_input_tokens"] / max(
            1, total_usage["cache_read_input_tokens"] + total_usage["input_tokens"]
        )
        print(f"   캐시 적중률: {ratio:.0%} (시스템 프롬프트 재사용 효과)")

    return 0 if not (all_errors or validation_errors) else 1


if __name__ == "__main__":
    sys.exit(main())
