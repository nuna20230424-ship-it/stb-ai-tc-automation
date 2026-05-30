"""사내 엑셀(KAON v0.8 형식) — 전 시트 한 번에 카탈로그 import.

업데이트 53: 100% 자동화 목표 — 25 시트(505건) 중 _제외 시트 빼고 24 시트(480건)를
한 번에 v2.2 schema로 변환.

사용:
    python -m tools.excel_importer.bulk \\
        --input "~/Downloads/사내-TC.xlsx" \\
        --output drafts/kaon-all.json \\
        --merge infrastructure/notebook-gateway/data/scenarios-catalog.json \\
        --header-row 7

각 시트마다 다음을 자동 결정:
- force-category: KAON_SHEET_TO_CATEGORY 매핑 테이블 사용
- id-prefix: f"kaon_{slug}" (시트명을 slug로 변환)
- default-priority: P2 (소스에서 미입력인 경우 폴백)
- default-sla: 시트별 가이드라인 (시동 시나리오는 길게, UI는 짧게)
- skip 시트: SKIP_SHEETS (이름에 _제외 포함 등)

산출:
- 단일 JSON (전체 통합) — 카탈로그와 dry-run 머지 미리보기
- 시트별 통과/skip 카운트 요약
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.excel_importer.column_map import DEFAULT_MAP, ColumnMap
    from tools.excel_importer.importer import direct_map_row, load_rows
else:
    from .column_map import DEFAULT_MAP, ColumnMap
    from .importer import direct_map_row, load_rows


# ──────────────────────────────────────────────────────────────
# KAON v0.8 시트 → v2.2 카테고리 매핑 + 옵션 가이드
# ──────────────────────────────────────────────────────────────

KAON_SHEET_TO_CATEGORY: dict[str, tuple[str, str, int]] = {
    # (force_category, id_prefix, default_sla_ms)
    "채널": ("EPG", "kaon_channel", 3000),
    "OTT": ("OTT", "kaon_ott", 5000),
    "VOD": ("OTT", "kaon_vod", 5000),
    "음성인식": ("Voice", "kaon_voice", 5000),
    "자녀안심 설정": ("Parental", "kaon_parental", 3000),
    "안정성": ("Power", "kaon_stability", 60000),  # 장시간 시나리오
    "펌웨어 업그레이드": ("Firmware", "kaon_firmware", 300000),  # 5분
    "부팅": ("Power", "kaon_boot", 60000),
    "POWER": ("Power", "kaon_power", 30000),
    "오디오": ("Audio", "kaon_audio", 3000),
    "해상도": ("Display", "kaon_display", 5000),
    "블루투스": ("Bluetooth", "kaon_bt", 10000),
    "RCU": ("RCU", "kaon_rcu", 2000),
    "네트워크": ("Network", "kaon_network", 10000),
    "홈_채널_VOD설정": ("Home", "kaon_home", 3000),
    "First I AD": ("Home", "kaon_ad", 5000),
    "AI 화질 최적화_Genie A+": ("AI", "kaon_ai_pq", 5000),
    "AI 사운드 최적화_Genie A+": ("AI", "kaon_ai_audio", 5000),
    "AI 실시간 자막_Genie A+": ("AI", "kaon_ai_caption", 5000),
    "시력 보호 모드_Genie A+": ("AI", "kaon_ai_eyecare", 3000),
    "목소리 강조_Genie A+": ("AI", "kaon_ai_voice_boost", 3000),
    "AI 시청 퀵모드_Genie A+": ("AI", "kaon_ai_quick", 3000),
    "AI 음성 가전 제어_Genie A+": ("Voice", "kaon_ai_homectl", 8000),
    "QAT": ("Firmware", "kaon_qat", 60000),
}

# 시트 이름에 이 토큰이 있으면 skip (manual_only / 제외)
SKIP_TOKENS = ["_제외", "(제외)"]


def is_skip(sheet: str) -> bool:
    return any(t in sheet for t in SKIP_TOKENS)


def kaon_column_map() -> ColumnMap:
    """KAON v0.8 표준 한국어 컬럼명."""
    return ColumnMap(
        id="TC ID",
        category="대분류",
        priority="중요도",
        expected="예상 결과",
        sla_ms="SLA (ms)",  # KAON 에는 없는 컬럼 — default-sla로 폴백
        preconditions="기능 범위(사전조건)",
        steps="테스트케이스 및 절차",
    )


# ──────────────────────────────────────────────────────────────
# Bulk import 로직
# ──────────────────────────────────────────────────────────────

def import_sheet(
    path: Path, sheet: str, *,
    header_row: int,
    force_category: str,
    id_prefix: str,
    default_priority: str,
    default_sla: int,
) -> tuple[list[dict], int]:
    """한 시트 → list[scenario dict] + skip count."""
    cmap = kaon_column_map()
    rows = load_rows(path, sheet=sheet, header_row=header_row)
    partial = [
        direct_map_row(
            r, cmap,
            force_category=force_category,
            default_priority=default_priority,
            default_sla=default_sla,
            id_prefix=id_prefix,
        )
        for r in rows
    ]
    ok = [p for p in partial if p is not None]
    skipped = len(partial) - len(ok)
    return ok, skipped


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="kaon-bulk-importer",
        description="KAON 사내 엑셀 → 전 시트 일괄 v2.2 카탈로그 변환",
    )
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path,
                   help="통합 JSON 출력 경로 (전 시트 머지)")
    p.add_argument("--header-row", type=int, default=7,
                   help="KAON v0.8 기본 7 (상단 7행 통계 요약 skip)")
    p.add_argument("--default-priority", default="P2",
                   choices=["P1", "P2", "P3"])
    p.add_argument("--merge", type=Path, default=None,
                   help="기존 카탈로그와 dry-run 머지 미리보기 출력")
    p.add_argument("--only", default=None,
                   help="콤마 구분 시트 이름 화이트리스트 (디버그)")
    args = p.parse_args(argv)

    try:
        import pandas as pd
    except ImportError as e:
        print(f"❌ pandas 미설치: {e}", file=sys.stderr)
        return 2

    xl = pd.ExcelFile(args.input)
    only = set(args.only.split(",")) if args.only else None

    print(f"📥 {args.input.name} — {len(xl.sheet_names)}개 시트 발견")
    print()

    all_scenarios: list[dict] = []
    summary: list[tuple[str, int, int, str, str]] = []
    # (sheet, ok, skipped, category, status)

    for sheet in xl.sheet_names:
        if only and sheet not in only:
            continue

        if is_skip(sheet):
            summary.append((sheet, 0, 0, "-", "SKIP (manual_only)"))
            continue

        if sheet not in KAON_SHEET_TO_CATEGORY:
            summary.append((sheet, 0, 0, "-", "UNMAPPED (편집 필요)"))
            continue

        cat, prefix, default_sla = KAON_SHEET_TO_CATEGORY[sheet]
        try:
            ok, skipped = import_sheet(
                args.input, sheet,
                header_row=args.header_row,
                force_category=cat,
                id_prefix=prefix,
                default_priority=args.default_priority,
                default_sla=default_sla,
            )
        except Exception as e:
            summary.append((sheet, 0, 0, cat, f"ERROR: {e}"))
            continue

        all_scenarios.extend(ok)
        status = "OK" if skipped == 0 else f"{skipped} skip"
        summary.append((sheet, len(ok), skipped, cat, status))

    # ID 중복 검출 (시트 간)
    seen: dict[str, str] = {}  # id → first-sheet
    dupes: list[tuple[str, str, str]] = []
    for sc in all_scenarios:
        if sc["id"] in seen:
            dupes.append((sc["id"], seen[sc["id"]], "?"))
        else:
            seen[sc["id"]] = sc["id"]

    # 결과 출력
    print(f"{'시트':35s} {'rows':>5s} {'skip':>5s} {'category':>10s}  {'status'}")
    print("-" * 80)
    for sheet, ok, sk, cat, status in summary:
        print(f"{sheet:35s} {ok:>5d} {sk:>5d} {cat:>10s}  {status}")

    print()
    print(f"📊 합계: {len(all_scenarios)} 시나리오 (시트 간 ID 중복 {len(dupes)}건)")
    if dupes:
        print("   ⚠️  ID 중복 — id_prefix 미스매칭 가능. 상위 5건:")
        for d in dupes[:5]:
            print(f"     {d}")

    # 출력
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(all_scenarios, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n✅ 통합 JSON: {args.output}")

    # 머지 미리보기
    if args.merge:
        if not args.merge.exists():
            print(f"\n⚠️  머지 대상 카탈로그 없음: {args.merge}")
        else:
            existing = json.loads(args.merge.read_text(encoding="utf-8"))
            existing_ids = {s.get("id") for s in existing if isinstance(s, dict)}
            new_ids = {s["id"] for s in all_scenarios}
            additions = sorted(new_ids - existing_ids)
            conflicts = sorted(new_ids & existing_ids)
            print(f"\n🔀 머지 미리보기 — 기존 {len(existing)}건 + 신규 {len(all_scenarios)}건")
            print(f"   추가 가능: {len(additions)}건")
            print(f"   ID 충돌  : {len(conflicts)}건")
            print(f"   머지 후 : {len(existing) + len(additions)}건")
            if conflicts[:5]:
                print(f"   충돌 예: {conflicts[:5]}")

    return 0 if not dupes else 1


if __name__ == "__main__":
    sys.exit(main())
