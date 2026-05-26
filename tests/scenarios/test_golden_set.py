"""골든셋 회귀 테스트 — 임계 변경 시 안전망.

각 골든셋 아이템을 detection-mcp에 보내 verdict가 ground truth와 일치하는지 검증.
임계(HARD_NORMAL/HARD_ANOMALY) 또는 detection-mcp 로직 변경 시 깨지면 PR 차단 신호.

골든셋이 비어 있으면 (실 STB 캡처 도착 전) 전부 skip.

실행:
  pytest -m golden_set
  pytest -m golden_set --backend-only   # detection-mcp만 필요, 게이트웨이는 skip
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.golden_set.schema import GoldenItem, golden_set_root, load_all  # noqa: E402


def _golden_items() -> list[GoldenItem]:
    return load_all()


GOLDEN_ITEMS = _golden_items()


def _item_id(item: GoldenItem) -> str:
    # pytest 노드 ID에 노출되는 라벨
    return f"{item.scenario_id}/{Path(item.image_path).parent.name}"


@pytest.mark.golden_set
@pytest.mark.skipif(not GOLDEN_ITEMS,
                     reason="골든셋 비어있음 — label_cli로 라벨 후 재실행")
@pytest.mark.parametrize("item", GOLDEN_ITEMS, ids=[_item_id(i) for i in GOLDEN_ITEMS])
def test_verdict_matches_ground_truth(item: GoldenItem, backend):
    """detection-mcp /check/screen verdict == ground_truth_verdict 검증."""
    image_path = golden_set_root() / item.image_path
    assert image_path.exists(), f"이미지 누락: {image_path}"

    # 카탈로그에서 expected / expected_keywords 조회 (룰 tier 입력 일관성)
    catalog = (_REPO_ROOT
               / "infrastructure/notebook-gateway/data/scenarios-catalog.json")
    import json
    catalog_data = json.loads(catalog.read_text(encoding="utf-8")) if catalog.exists() else []
    scenario_meta = next((s for s in catalog_data if s["id"] == item.scenario_id), {})

    verdict = backend.detection.check_screen(
        scenario=item.scenario_id,
        image_path=image_path,
        firmware=item.firmware,
        expected=scenario_meta.get("expected"),
        expected_keywords=scenario_meta.get("expected_keywords") or None,
    )

    assert verdict["verdict"] == item.ground_truth_verdict, (
        f"verdict 불일치 — ground_truth={item.ground_truth_verdict} "
        f"detection={verdict['verdict']} tier={verdict.get('tier')} "
        f"score={verdict.get('best_score'):.4f}  "
        f"이미지: {item.image_path}"
    )
