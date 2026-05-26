"""Golden set 스키마 — 사람이 라벨한 (image, ground_truth) 페어.

디렉토리 레이아웃:

    tests/baselines/golden_set/
    ├── <scenario_id>/
    │   ├── <label_id>/
    │   │   ├── image.png
    │   │   └── meta.json   ← GoldenItem
    │   └── ...
    └── .cache/              ← tune_thresholds 결과 캐시

GoldenItem.image_path는 golden_set 루트 기준 상대경로 (예: `epg_open_7day/2026-05-26T180000/image.png`).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["normal", "anomaly"]
ExpectedTier = Literal["embedding", "rule", "vision"]


class GoldenItem(BaseModel):
    """골든셋 1건 — 시나리오 × 화면 × ground truth.

    detection_snapshot은 라벨링 시점의 detection-mcp 응답 — 튜닝 시 캐시로 활용.
    이후 detection-mcp 버전 변경 시 `--refresh-cache`로 재수집.
    """
    scenario_id: str = Field(min_length=3)
    image_path: str = Field(
        description="golden_set 루트 기준 상대경로. <scenario>/<label_id>/image.png 권장"
    )
    firmware: str
    ground_truth_verdict: Verdict
    ground_truth_tier: ExpectedTier = Field(
        description="이상적인 판정 tier — embedding이 가장 바람직, vision은 최후의 보루"
    )
    notes: str | None = None
    labeler: str
    labeled_at: datetime
    evidence_dir: str | None = Field(
        default=None,
        description="evidence-bundler로 만든 디렉토리에서 유래 시 그 경로"
    )
    detection_snapshot: dict | None = Field(
        default=None,
        description="라벨링 당시 detection-mcp /check/screen 전체 응답 (튜닝 캐시)"
    )


def golden_set_root() -> Path:
    """tests/baselines/golden_set 절대 경로."""
    return (Path(__file__).resolve().parents[2]
            / "tests" / "baselines" / "golden_set")


def load_all(root: Path | None = None) -> list[GoldenItem]:
    """golden_set/**/meta.json 모두 로드. 파일이 없으면 빈 리스트."""
    base = root or golden_set_root()
    if not base.exists():
        return []
    items: list[GoldenItem] = []
    for meta in sorted(base.glob("**/meta.json")):
        items.append(GoldenItem.model_validate_json(meta.read_text(encoding="utf-8")))
    return items


def save_item(item: GoldenItem, *, image_bytes: bytes | None = None,
               root: Path | None = None) -> Path:
    """meta.json (+ optional image.png) 저장 후 디렉토리 경로 반환.

    item.image_path가 가리키는 디렉토리에 저장 — 호출자가 unique한 label_id 생성 책임.
    """
    base = root or golden_set_root()
    item_dir = (base / item.image_path).parent
    item_dir.mkdir(parents=True, exist_ok=True)
    if image_bytes is not None:
        (item_dir / "image.png").write_bytes(image_bytes)
    (item_dir / "meta.json").write_text(
        item.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return item_dir


def make_label_id(when: datetime | None = None) -> str:
    """`2026-05-26T180000` 형식 — 정렬 가능하고 파일명 안전."""
    when = when or datetime.now()
    return when.strftime("%Y-%m-%dT%H%M%S")
