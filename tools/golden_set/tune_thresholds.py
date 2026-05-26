"""골든셋 기반 임계 grid search.

흐름:
  1. load_all() — golden_set/**/meta.json 로드
  2. 각 항목의 detection_snapshot 사용 (없거나 --refresh-cache 시 detection-mcp 호출)
  3. HARD_NORMAL × HARD_ANOMALY grid에 대해 replay_verdict → ground truth와 비교
  4. metric: accuracy / fp / fn / gray_zone_ratio
  5. objective 별 TOP-N + 환경변수 명령 출력

사용:
  python -m tools.golden_set.tune_thresholds
  python -m tools.golden_set.tune_thresholds --objective fn-minimize
  python -m tools.golden_set.tune_thresholds --refresh-cache
  python -m tools.golden_set.tune_thresholds --grid-step 0.005 --top 5

⚠️ snapshot이 좁은 회색 지대(예: HN=0.96, HA=0.85)에서 찍혔다면 그 범위 밖
   item의 rule_match/vision_verdict가 비어 있다 → replay 결과가 rule-fallthrough로 떨어진다.
   완전한 grid search를 원하면 라벨링 시 임시로 (HN=0.99, HA=0.99) 가깝게 설정.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.golden_set.schema import GoldenItem, golden_set_root, load_all  # noqa: E402
from tools.golden_set.replay import replay_verdict  # noqa: E402


# ──────────────────────────────────────────────────────────────
# detection-mcp 호출 (snapshot 부재 시)
# ──────────────────────────────────────────────────────────────

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


def _load_catalog_meta() -> dict[str, tuple[str | None, list[str] | None]]:
    cat = REPO_ROOT / "infrastructure/notebook-gateway/data/scenarios-catalog.json"
    if not cat.exists():
        return {}
    return {
        s["id"]: (s.get("expected"), s.get("expected_keywords") or None)
        for s in json.loads(cat.read_text(encoding="utf-8"))
    }


def ensure_snapshots(items: list[GoldenItem], *, refresh: bool,
                       detection_url: str) -> list[GoldenItem]:
    """snapshot 없거나 refresh 요청 시 detection-mcp 호출해 채워서 새 리스트 반환.

    원본 meta.json은 갱신하지 않는다 (호출자가 명시적으로 처리).
    """
    catalog_meta = _load_catalog_meta()
    out: list[GoldenItem] = []
    for item in items:
        if item.detection_snapshot and not refresh:
            out.append(item)
            continue
        image_path = golden_set_root() / item.image_path
        expected, keywords = catalog_meta.get(item.scenario_id, (None, None))
        snap = _call_detection(
            image_path, item.scenario_id, item.firmware,
            expected, keywords, detection_url,
        )
        out.append(item.model_copy(update={"detection_snapshot": snap}))
    return out


# ──────────────────────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Metrics:
    hard_normal: float
    hard_anomaly: float
    n: int
    tp: int      # ground=anomaly, pred=anomaly
    tn: int      # ground=normal,  pred=normal
    fp: int      # ground=normal,  pred=anomaly
    fn: int      # ground=anomaly, pred=normal
    gray: int    # tier ∈ {rule, vision, rule-fallthrough}
    # tier mismatch 별도 카운트 — embedding이 ground이면 embedding로 처리되어야 이상적
    tier_mismatch: int

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.n if self.n else 0.0

    @property
    def fp_rate(self) -> float:
        normals = self.tn + self.fp
        return self.fp / normals if normals else 0.0

    @property
    def fn_rate(self) -> float:
        anomalies = self.tp + self.fn
        return self.fn / anomalies if anomalies else 0.0

    @property
    def gray_zone_ratio(self) -> float:
        return self.gray / self.n if self.n else 0.0


def evaluate(items: list[GoldenItem], hard_normal: float, hard_anomaly: float,
              vision_enabled: bool = True) -> Metrics:
    tp = tn = fp = fn = gray = mismatch = 0
    for it in items:
        snap = it.detection_snapshot or {}
        replay = replay_verdict(
            best_score=float(snap.get("best_score", 0.0)),
            rule_match=snap.get("rule_match"),
            vision_verdict=snap.get("vision_verdict"),
            hard_normal=hard_normal,
            hard_anomaly=hard_anomaly,
            vision_enabled=vision_enabled,
        )
        gt = it.ground_truth_verdict
        if gt == "anomaly" and replay.verdict == "anomaly":
            tp += 1
        elif gt == "normal" and replay.verdict == "normal":
            tn += 1
        elif gt == "normal" and replay.verdict == "anomaly":
            fp += 1
        else:
            fn += 1
        if replay.tier in ("rule", "vision", "rule-fallthrough"):
            gray += 1
        if it.ground_truth_tier != replay.tier and replay.tier != "rule-fallthrough":
            mismatch += 1
    return Metrics(
        hard_normal=hard_normal, hard_anomaly=hard_anomaly,
        n=len(items), tp=tp, tn=tn, fp=fp, fn=fn,
        gray=gray, tier_mismatch=mismatch,
    )


# ──────────────────────────────────────────────────────────────
# Grid search + 객체 선택
# ──────────────────────────────────────────────────────────────

OBJECTIVES = {
    "accuracy":      lambda m: -m.accuracy,                       # higher better
    "fn-minimize":   lambda m: (m.fn_rate, -m.accuracy),           # FN 최소 우선
    "balanced":      lambda m: (-m.accuracy + m.gray_zone_ratio),  # 정확도+회색 지대 균형
    "gray-minimize": lambda m: (m.gray_zone_ratio, -m.accuracy),   # 회색 지대 최소 우선
}


def grid_search(items: list[GoldenItem], *,
                 hn_range: tuple[float, float] = (0.85, 0.99),
                 ha_range: tuple[float, float] = (0.75, 0.92),
                 step: float = 0.01,
                 vision_enabled: bool = True) -> list[Metrics]:
    """모든 (HARD_NORMAL > HARD_ANOMALY) 조합에 대해 Metrics 산출."""
    def _frange(lo: float, hi: float, st: float) -> list[float]:
        n = round((hi - lo) / st) + 1
        return [round(lo + i * st, 6) for i in range(n)]

    out: list[Metrics] = []
    for hn in _frange(*hn_range, step):
        for ha in _frange(*ha_range, step):
            if ha >= hn:
                continue  # HARD_ANOMALY < HARD_NORMAL 강제
            out.append(evaluate(items, hn, ha, vision_enabled))
    return out


def rank(results: list[Metrics], objective: str) -> list[Metrics]:
    key = OBJECTIVES[objective]
    return sorted(results, key=key)


# ──────────────────────────────────────────────────────────────
# 출력
# ──────────────────────────────────────────────────────────────

def _format_row(m: Metrics) -> str:
    return (f"HN={m.hard_normal:.3f}  HA={m.hard_anomaly:.3f}  "
            f"acc={m.accuracy:.3f}  fp={m.fp_rate:.3f}  fn={m.fn_rate:.3f}  "
            f"gray={m.gray_zone_ratio:.3f}  mismatch={m.tier_mismatch}")


def print_top(ranked: list[Metrics], top: int) -> None:
    print(f"\n📊 TOP {top}:")
    for i, m in enumerate(ranked[:top], 1):
        print(f"  {i:2}. {_format_row(m)}")


def print_env_export(m: Metrics) -> None:
    print("\n💡 환경변수 적용:")
    print(f"  export THRESHOLD_HARD_NORMAL={m.hard_normal}")
    print(f"  export THRESHOLD_HARD_ANOMALY={m.hard_anomaly}")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="tune-thresholds")
    ap.add_argument("--objective", choices=sorted(OBJECTIVES), default="balanced")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--grid-step", type=float, default=0.01)
    ap.add_argument("--hn-range", nargs=2, type=float, default=(0.85, 0.99))
    ap.add_argument("--ha-range", nargs=2, type=float, default=(0.75, 0.92))
    ap.add_argument("--refresh-cache", action="store_true",
                    help="detection-mcp를 다시 호출해 snapshot 갱신 (느림)")
    ap.add_argument("--detection-url",
                    default=os.getenv("DETECTION_MCP_URL", "http://10.0.10.50:8103"))
    ap.add_argument("--no-vision", action="store_true",
                    help="vision tier 비활성 가정으로 평가")
    ap.add_argument("--save-report", type=Path,
                    help="ranked 결과를 JSON으로 저장")
    args = ap.parse_args()

    items = load_all()
    if not items:
        print("❌ 골든셋이 비어있음. label_cli로 1건 이상 라벨 후 재시도",
              file=sys.stderr)
        return 2

    items = ensure_snapshots(items, refresh=args.refresh_cache,
                              detection_url=args.detection_url)
    n_with_snap = sum(1 for it in items if it.detection_snapshot)
    print(f"📋 골든셋: {len(items)}건 (snapshot {n_with_snap}/{len(items)})")
    if n_with_snap < len(items):
        print("  ⚠️  snapshot 없는 항목 — replay 시 score=0.0 → anomaly 강제. "
              "--refresh-cache 권장")

    results = grid_search(
        items,
        hn_range=tuple(args.hn_range),
        ha_range=tuple(args.ha_range),
        step=args.grid_step,
        vision_enabled=not args.no_vision,
    )
    ranked = rank(results, args.objective)

    print(f"\n🎯 objective={args.objective}  (총 {len(results)} 조합 평가)")
    print_top(ranked, args.top)
    print_env_export(ranked[0])

    if args.save_report:
        args.save_report.write_text(
            json.dumps([m.__dict__ for m in ranked], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n📝 리포트 저장: {args.save_report}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
