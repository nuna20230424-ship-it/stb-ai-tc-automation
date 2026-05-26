"""detection-mcp의 verdict 결정 로직을 로컬에서 재현 — 임계 grid search용.

라벨링 시 한 번 detection-mcp /check/screen을 호출해 raw 응답을 snapshot에 저장하면,
이후 임계만 바꾸며 수천 번 재평가할 수 있다.

⚠️ 한계: detection-mcp는 임계에 따라 rule_match/vision_verdict를 "계산 자체를 안 함".
   따라서 snapshot이 (HARD_NORMAL=0.96, HARD_ANOMALY=0.85)에서 찍혔다면
   그때의 회색 지대 항목만 rule_match/vision_verdict가 채워져 있음.
   더 넓은 회색 지대로 재평가할 때 rule/vision 정보가 비어 있으면
   `vision_verdict가 None` → rule-fallthrough로 처리한다.

   완전 grid search를 원하면 라벨링 시 임시로 임계를 (0.99, 0.99)에 가깝게 설정해
   모든 항목이 회색 지대를 거치도록 snapshot 수집 (docs/31 §4 참고).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReplayTier = Literal["embedding", "rule", "vision", "rule-fallthrough"]
ReplayVerdict = Literal["normal", "anomaly"]


@dataclass(frozen=True)
class ReplayResult:
    verdict: ReplayVerdict
    tier: ReplayTier


def replay_verdict(
    *,
    best_score: float,
    rule_match: dict | None,
    vision_verdict: dict | None,
    hard_normal: float,
    hard_anomaly: float,
    vision_enabled: bool = True,
) -> ReplayResult:
    """detection-mcp의 3-tier 로직을 임계만 바꿔 재실행.

    rule_match: snapshot에 저장된 것 (raw description으로 매번 같은 결과).
    vision_verdict: snapshot에 저장된 것 (raw image로 매번 같은 결과).
    """
    # Tier 1: 임베딩
    if best_score >= hard_normal:
        return ReplayResult("normal", "embedding")
    if best_score < hard_anomaly:
        return ReplayResult("anomaly", "embedding")

    # Tier 2: 룰
    if rule_match:
        return ReplayResult("normal", "rule")

    # Tier 3: vision
    if vision_enabled and vision_verdict is not None:
        return ReplayResult(
            "normal" if vision_verdict.get("match") else "anomaly",
            "vision",
        )

    # vision 비활성 + 룰 실패 → 보수적 anomaly (detection-mcp main.py와 일치)
    return ReplayResult("anomaly", "rule-fallthrough")
