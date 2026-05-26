"""골든셋 라벨링 CLI — 캡처/evidence 번들을 ground truth와 짝지어 저장.

사용 1) 단일 캡처:
  python -m tools.golden_set.label_cli \\
      --scenario epg_open_7day \\
      --image path/to/capture.png \\
      --firmware v1.2.3 \\
      --labeler keonhee.cho@kaongroup.com

사용 2) evidence 번들에서 (verdict 비교 가시화):
  python -m tools.golden_set.label_cli \\
      --from-evidence evidence/2026-05-26_epg_open_7day_anomaly \\
      --labeler keonhee.cho@kaongroup.com

사용 3) 비대화 (배치 라벨링용):
  python -m tools.golden_set.label_cli \\
      --scenario epg_open_7day --image ./shot.png \\
      --firmware v1.2.3 --labeler me@x.com \\
      --verdict normal --tier embedding --yes

흐름:
  1. detection-mcp /check/screen 호출 → 현재 verdict/tier/score 출력
  2. (대화 모드) macOS면 `open` 으로 이미지 미리보기
  3. ground truth 입력: verdict + tier + notes
  4. tests/baselines/golden_set/<scenario>/<label_id>/ 에 image.png + meta.json 저장
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.golden_set.schema import (  # noqa: E402
    GoldenItem, golden_set_root, make_label_id, save_item,
)


VERDICT_MAP = {"n": "normal", "normal": "normal", "a": "anomaly", "anomaly": "anomaly"}
TIER_MAP = {"e": "embedding", "embedding": "embedding",
            "r": "rule", "rule": "rule",
            "v": "vision", "vision": "vision"}


def _ask(prompt: str, valid: dict[str, str]) -> str:
    while True:
        v = input(prompt).strip().lower()
        if v in valid:
            return valid[v]
        print(f"  ↑ {sorted(set(valid.values()))} 중 하나로 입력하세요.")


def _call_detection(image_path: Path, scenario: str, firmware: str,
                     expected: str | None, expected_keywords: list[str] | None,
                     detection_url: str) -> dict:
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    payload: dict = {"scenario": scenario, "image_base64": b64, "firmware": firmware}
    if expected:
        payload["expected"] = expected
    if expected_keywords:
        payload["expected_keywords"] = expected_keywords
    r = httpx.post(f"{detection_url.rstrip('/')}/check/screen",
                   json=payload, timeout=240)
    r.raise_for_status()
    return r.json()


def _load_scenario_meta(scenario_id: str) -> tuple[str | None, list[str] | None]:
    """카탈로그에서 expected / expected_keywords 추출. 시나리오 미존재 시 (None, None)."""
    cat = REPO_ROOT / "infrastructure/notebook-gateway/data/scenarios-catalog.json"
    if not cat.exists():
        return (None, None)
    for s in json.loads(cat.read_text(encoding="utf-8")):
        if s["id"] == scenario_id:
            return s.get("expected"), s.get("expected_keywords") or None
    return (None, None)


def _open_preview(image_path: Path) -> None:
    """macOS는 open, 그 외 환경은 print만."""
    if sys.platform == "darwin" and shutil.which("open"):
        subprocess.run(["open", str(image_path)], check=False)
    else:
        print(f"  (미리보기 자동 열기 미지원 — 별도 뷰어로 {image_path} 확인)")


def _from_evidence(evidence_dir: Path) -> tuple[str, Path, str | None]:
    """evidence 번들에서 (scenario_id, image_path, firmware) 추출.

    evidence-bundler의 scenario.json + capture/*.png 구조 가정.
    """
    meta_path = evidence_dir / "scenario.json"
    if not meta_path.exists():
        raise SystemExit(f"❌ evidence_dir에 scenario.json 없음: {evidence_dir}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    scenario_id = meta.get("scenario") or meta.get("id")
    if not scenario_id:
        raise SystemExit(f"❌ scenario.json에서 시나리오 ID를 못 찾음")

    cap_dir = evidence_dir / "capture"
    images = sorted(cap_dir.glob("*.png")) if cap_dir.exists() else []
    if not images:
        raise SystemExit(f"❌ {cap_dir}에 PNG 캡처가 없음")
    image_path = images[-1]  # 마지막(=결과) 프레임

    firmware = meta.get("firmware")
    return scenario_id, image_path, firmware


def main() -> int:
    load_dotenv()

    ap = argparse.ArgumentParser(prog="golden-label",
        description="골든셋 라벨링 — detection-mcp 응답과 ground truth 짝지어 저장")
    ap.add_argument("--scenario")
    ap.add_argument("--image", type=Path)
    ap.add_argument("--firmware")
    ap.add_argument("--from-evidence", type=Path,
                    help="evidence-bundler 디렉토리에서 scenario/image 자동 추출")
    ap.add_argument("--labeler", required=True,
                    help="라벨러 식별자 (이메일/핸들)")
    ap.add_argument("--detection-url",
                    default=os.getenv("DETECTION_MCP_URL", "http://10.0.10.50:8103"))
    # 비대화 모드
    ap.add_argument("--verdict", choices=["normal", "anomaly"])
    ap.add_argument("--tier", choices=["embedding", "rule", "vision"])
    ap.add_argument("--notes", default=None)
    ap.add_argument("--yes", action="store_true",
                    help="확인 prompt 없이 저장 (비대화 모드)")
    ap.add_argument("--no-preview", action="store_true",
                    help="macOS open으로 이미지 미리보기 띄우지 않음")
    ap.add_argument("--no-detection-call", action="store_true",
                    help="detection-mcp 호출 생략 (오프라인 라벨링)")
    args = ap.parse_args()

    # 1. 입력 정규화
    if args.from_evidence:
        scenario_id, image_path, firmware_from_evidence = _from_evidence(args.from_evidence)
        firmware = args.firmware or firmware_from_evidence or "unknown"
        evidence_dir = str(args.from_evidence.resolve())
    else:
        if not (args.scenario and args.image and args.firmware):
            ap.error("--from-evidence 가 없으면 --scenario --image --firmware 모두 필요")
        scenario_id = args.scenario
        image_path = args.image
        firmware = args.firmware
        evidence_dir = None

    if not image_path.exists():
        raise SystemExit(f"❌ 이미지 없음: {image_path}")

    # 2. detection-mcp 호출 (사용자 비교 + snapshot 저장)
    snapshot: dict | None = None
    if not args.no_detection_call:
        expected, expected_keywords = _load_scenario_meta(scenario_id)
        try:
            snapshot = _call_detection(image_path, scenario_id, firmware,
                                         expected, expected_keywords, args.detection_url)
            print("\n🤖 detection-mcp 현재 판정:")
            print(f"   verdict={snapshot.get('verdict')}  tier={snapshot.get('tier')}")
            print(f"   score={snapshot.get('best_score'):.4f}  "
                  f"confidence={snapshot.get('confidence'):.4f}")
            if snapshot.get("rule_match"):
                rm = snapshot["rule_match"]
                print(f"   rule_match: hit_ratio={rm.get('hit_ratio'):.2f}  "
                      f"matched={rm.get('matched_keywords')}")
        except Exception as e:
            print(f"⚠️  detection-mcp 호출 실패 ({e}) — snapshot 없이 진행", file=sys.stderr)

    # 3. 이미지 미리보기
    if not args.no_preview:
        _open_preview(image_path)

    # 4. ground truth 입력
    if args.verdict and args.tier:
        verdict = args.verdict
        tier = args.tier
        notes = args.notes
    else:
        print("\n👤 Ground truth 입력:")
        verdict = _ask("  실제 verdict? [n]ormal / [a]nomaly: ", VERDICT_MAP)
        tier = _ask("  이상적인 tier? [e]mbedding / [r]ule / [v]ision: ", TIER_MAP)
        notes_input = input("  notes (Enter = 생략): ").strip()
        notes = notes_input or args.notes

    # 5. 저장
    label_id = make_label_id()
    rel_image = f"{scenario_id}/{label_id}/image.png"
    item = GoldenItem(
        scenario_id=scenario_id,
        image_path=rel_image,
        firmware=firmware,
        ground_truth_verdict=verdict,
        ground_truth_tier=tier,
        notes=notes,
        labeler=args.labeler,
        labeled_at=datetime.now(),
        evidence_dir=evidence_dir,
        detection_snapshot=snapshot,
    )

    target_dir = golden_set_root() / scenario_id / label_id
    if not args.yes:
        print(f"\n💾 저장 위치: {target_dir.relative_to(REPO_ROOT)}")
        if input("진행? [Y/n]: ").strip().lower() in ("n", "no"):
            print("취소")
            return 1

    image_bytes = image_path.read_bytes()
    saved = save_item(item, image_bytes=image_bytes)
    print(f"✅ 저장 완료: {saved.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
