"""골든셋 도구 단위 테스트 — schema / replay / tune_thresholds.evaluate."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from tools.golden_set.replay import replay_verdict
from tools.golden_set.schema import GoldenItem, load_all, make_label_id, save_item
from tools.golden_set.tune_thresholds import OBJECTIVES, evaluate, grid_search, rank


# ─── replay_verdict ────────────────────────────────────────────

def test_replay_hard_normal_short_circuits_to_embedding():
    r = replay_verdict(best_score=0.97, rule_match=None, vision_verdict=None,
                        hard_normal=0.96, hard_anomaly=0.85)
    assert r.verdict == "normal" and r.tier == "embedding"


def test_replay_hard_anomaly_short_circuits_to_embedding():
    r = replay_verdict(best_score=0.80, rule_match=None, vision_verdict=None,
                        hard_normal=0.96, hard_anomaly=0.85)
    assert r.verdict == "anomaly" and r.tier == "embedding"


def test_replay_gray_zone_falls_to_rule_when_rule_match_present():
    r = replay_verdict(
        best_score=0.90, rule_match={"hit_ratio": 0.5}, vision_verdict=None,
        hard_normal=0.96, hard_anomaly=0.85,
    )
    assert r.verdict == "normal" and r.tier == "rule"


def test_replay_gray_zone_falls_to_vision_when_no_rule_match():
    r = replay_verdict(
        best_score=0.90, rule_match=None, vision_verdict={"match": True},
        hard_normal=0.96, hard_anomaly=0.85,
    )
    assert r.verdict == "normal" and r.tier == "vision"

    r2 = replay_verdict(
        best_score=0.90, rule_match=None, vision_verdict={"match": False},
        hard_normal=0.96, hard_anomaly=0.85,
    )
    assert r2.verdict == "anomaly" and r2.tier == "vision"


def test_replay_vision_disabled_falls_through_to_anomaly():
    r = replay_verdict(
        best_score=0.90, rule_match=None, vision_verdict=None,
        hard_normal=0.96, hard_anomaly=0.85, vision_enabled=False,
    )
    assert r.verdict == "anomaly" and r.tier == "rule-fallthrough"


# ─── schema save/load round-trip ───────────────────────────────

def _make_item(scenario: str = "epg_open_7day",
                gt_verdict: str = "normal",
                gt_tier: str = "embedding",
                label_id: str | None = None,
                snapshot: dict | None = None) -> GoldenItem:
    label_id = label_id or make_label_id()
    return GoldenItem(
        scenario_id=scenario,
        image_path=f"{scenario}/{label_id}/image.png",
        firmware="v1.2.3",
        ground_truth_verdict=gt_verdict,  # type: ignore
        ground_truth_tier=gt_tier,         # type: ignore
        notes=None,
        labeler="test@example.com",
        labeled_at=datetime(2026, 5, 26, 18, 0, 0),
        detection_snapshot=snapshot,
    )


def test_save_and_load_roundtrip(tmp_path: Path):
    item = _make_item(label_id="2026-05-26T180000",
                       snapshot={"verdict": "normal", "best_score": 0.97,
                                 "tier": "embedding", "rule_match": None,
                                 "vision_verdict": None})
    saved_dir = save_item(item, image_bytes=b"\x89PNG fake", root=tmp_path)
    assert (saved_dir / "meta.json").exists()
    assert (saved_dir / "image.png").exists()

    loaded = load_all(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].scenario_id == "epg_open_7day"
    assert loaded[0].detection_snapshot["best_score"] == 0.97


def test_load_empty_directory_returns_empty(tmp_path: Path):
    assert load_all(tmp_path) == []


def test_make_label_id_format():
    when = datetime(2026, 5, 26, 18, 30, 45)
    assert make_label_id(when) == "2026-05-26T183045"


def test_save_rejects_invalid_scenario_id():
    with pytest.raises(Exception):
        _make_item(scenario="a")  # min_length=3 위반


# ─── evaluate / grid_search ────────────────────────────────────

def _items_with_scores(scores_truth: list[tuple[float, str]]) -> list[GoldenItem]:
    out = []
    for i, (score, gt) in enumerate(scores_truth):
        out.append(_make_item(
            scenario=f"scn_{i:03d}",
            gt_verdict=gt,
            label_id=f"2026-05-26T1800{i:02d}",
            snapshot={"verdict": "normal" if score >= 0.96 else "anomaly",
                      "best_score": score, "tier": "embedding",
                      "rule_match": None, "vision_verdict": None},
        ))
    return out


def test_evaluate_perfect_separation():
    """모든 normal 점수 > HN, 모든 anomaly 점수 < HA → accuracy=1.0, gray=0."""
    items = _items_with_scores([
        (0.98, "normal"), (0.97, "normal"), (0.99, "normal"),
        (0.80, "anomaly"), (0.75, "anomaly"),
    ])
    m = evaluate(items, hard_normal=0.96, hard_anomaly=0.85)
    assert m.accuracy == 1.0
    assert m.fp == 0 and m.fn == 0
    assert m.gray == 0


def test_evaluate_counts_false_negatives_when_anomaly_misclassified():
    """anomaly가 normal로 분류되면 fn 증가."""
    items = _items_with_scores([
        (0.99, "normal"),
        (0.98, "anomaly"),  # HN=0.96 → predicted normal → fn
    ])
    m = evaluate(items, hard_normal=0.96, hard_anomaly=0.85)
    assert m.fn == 1 and m.tp == 0
    assert m.tn == 1 and m.fp == 0
    assert m.fn_rate == 1.0


def test_evaluate_counts_gray_zone():
    """gray zone (rule-fallthrough) 카운트 — vision_verdict 없으면 모두 fallthrough."""
    items = _items_with_scores([
        (0.90, "anomaly"),  # gray zone, no rule, no vision → rule-fallthrough anomaly
    ])
    m = evaluate(items, hard_normal=0.96, hard_anomaly=0.85)
    assert m.gray == 1
    assert m.tp == 1  # rule-fallthrough → anomaly, GT=anomaly, matches


def test_grid_search_skips_invalid_ranges():
    """HA >= HN 조합은 제외."""
    items = _items_with_scores([(0.97, "normal")])
    results = grid_search(items, hn_range=(0.90, 0.91), ha_range=(0.92, 0.93),
                           step=0.01)
    # 모든 HA(0.92, 0.93)가 모든 HN(0.90, 0.91)보다 크거나 같음 → 0건
    assert results == []


def test_grid_search_returns_combinations():
    items = _items_with_scores([(0.97, "normal"), (0.80, "anomaly")])
    results = grid_search(items, hn_range=(0.95, 0.97), ha_range=(0.85, 0.86),
                           step=0.01)
    # HN ∈ {0.95, 0.96, 0.97}, HA ∈ {0.85, 0.86} → 6 조합 (모두 HA < HN)
    assert len(results) == 6


def test_rank_objective_balanced_picks_best():
    """accuracy=1.0, gray=0 → balanced로 가장 좋은 점수."""
    items = _items_with_scores([
        (0.99, "normal"), (0.97, "normal"),
        (0.80, "anomaly"), (0.78, "anomaly"),
    ])
    results = grid_search(items, hn_range=(0.95, 0.98), ha_range=(0.85, 0.85),
                           step=0.01)
    ranked = rank(results, "balanced")
    best = ranked[0]
    assert best.accuracy == 1.0


def test_objectives_all_callable_on_metrics():
    items = _items_with_scores([(0.97, "normal"), (0.80, "anomaly")])
    m = evaluate(items, hard_normal=0.96, hard_anomaly=0.85)
    for name, fn in OBJECTIVES.items():
        _ = fn(m)  # 호출 가능 여부만 (예외 없으면 OK)
