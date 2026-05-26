"""벤치 실행 로직 — 순수 함수, provider 객체만 외부 주입.

흐름:
  golden_set 로드 → 각 항목 + provider 조합 호출 → ProviderResult 누적 → summarize
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tools.vision_bench.providers import VisionResponse

# detection-mcp tier 3와 동일한 yes/no 프롬프트 (main.py:_tier3_vision)
DEFAULT_PROMPT_TEMPLATE = (
    "다음 화면이 이 기대 결과와 부합하는지 yes/no로 답하세요.\n"
    "기대 결과: {expected}\n"
    "답변 형식: 'yes' 또는 'no' 한 단어로 시작하고, 이어서 짧은 근거."
)


@dataclass
class BenchItem:
    """벤치 1건 — 골든셋의 (image, expected, ground_truth)."""
    scenario: str
    image_path: Path
    expected: str
    ground_truth_yes: bool  # ground_truth_verdict == "normal"


@dataclass
class ProviderResult:
    provider: str
    model: str
    scenario: str
    response: VisionResponse
    predicted_yes: bool
    correct: bool


def parse_yes_no(text: str) -> bool:
    """detection-mcp main._tier3_vision과 동일 — 첫 단어 y/예/맞 시작이면 yes."""
    if not text:
        return False
    first = text.strip().split()[:1]
    return bool(first) and first[0].lower().startswith(("y", "예", "맞"))


def run_bench(items: list[BenchItem], providers: list,
               prompt_template: str = DEFAULT_PROMPT_TEMPLATE) -> list[ProviderResult]:
    """각 item × provider 조합 호출. error시 correct=False로 기록 (skip 아님)."""
    results: list[ProviderResult] = []
    for item in items:
        prompt = prompt_template.format(expected=item.expected)
        image_bytes = item.image_path.read_bytes()
        for p in providers:
            resp = p.describe(image_bytes, prompt)
            predicted = parse_yes_no(resp.description) if not resp.error else False
            correct = (predicted == item.ground_truth_yes) and not resp.error
            results.append(ProviderResult(
                provider=p.name, model=resp.model, scenario=item.scenario,
                response=resp, predicted_yes=predicted, correct=correct,
            ))
    return results


def summarize(results: list[ProviderResult]) -> dict:
    """(provider, model) 키 별 accuracy / latency p50·p95 / cost 집계."""
    by_key: dict[tuple[str, str], list[ProviderResult]] = {}
    for r in results:
        by_key.setdefault((r.provider, r.model), []).append(r)

    out: dict = {}
    for (provider, model), rs in by_key.items():
        n = len(rs)
        latencies = sorted(r.response.latency_ms for r in rs)
        errors = sum(1 for r in rs if r.response.error)
        out[f"{provider}/{model}"] = {
            "n": n,
            "accuracy": sum(1 for r in rs if r.correct) / n if n else 0.0,
            "errors": errors,
            "error_rate": errors / n if n else 0.0,
            "latency_p50_ms": latencies[len(latencies) // 2] if latencies else 0.0,
            "latency_p95_ms": latencies[int(0.95 * len(latencies))] if latencies else 0.0,
            "total_cost_usd": sum(r.response.cost_usd for r in rs),
            "cost_per_call_usd": (sum(r.response.cost_usd for r in rs) / n) if n else 0.0,
            "tokens_in_total": sum(r.response.tokens_in for r in rs),
            "tokens_out_total": sum(r.response.tokens_out for r in rs),
        }
    return out


# ──────────────────────────────────────────────────────────────
# Recommendation — accuracy 최우선, tie면 cost·latency
# ──────────────────────────────────────────────────────────────

def rank_summary(summary: dict, objective: str = "accuracy-first") -> list[tuple[str, dict]]:
    """summary dict를 objective 기준 정렬."""
    items = list(summary.items())
    if objective == "accuracy-first":
        # accuracy desc, error_rate asc, cost asc, latency asc
        items.sort(key=lambda kv: (
            -kv[1]["accuracy"], kv[1]["error_rate"],
            kv[1]["cost_per_call_usd"], kv[1]["latency_p50_ms"],
        ))
    elif objective == "cost-first":
        # cost asc, accuracy desc, latency asc
        items.sort(key=lambda kv: (
            kv[1]["cost_per_call_usd"], -kv[1]["accuracy"], kv[1]["latency_p50_ms"],
        ))
    elif objective == "latency-first":
        items.sort(key=lambda kv: (
            kv[1]["latency_p50_ms"], -kv[1]["accuracy"], kv[1]["cost_per_call_usd"],
        ))
    else:
        raise ValueError(f"알 수 없는 objective: {objective}")
    return items
