"""vision_bench 단위 테스트 — providers / runner / summarize / rank."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.vision_bench.providers import (
    ANTHROPIC_PRICING, GEMINI_PRICING, OPENAI_PRICING,
    AnthropicProvider, GeminiProvider, OllamaProvider, OpenAIProvider,
    PROVIDERS, VisionResponse,
    available_providers, compute_cost, make_provider,
)
from tools.vision_bench.runner import (
    BenchItem, ProviderResult,
    parse_yes_no, rank_summary, run_bench, summarize,
)


# ─── compute_cost ──────────────────────────────────────────────

def test_compute_cost_basic():
    # 1M tokens at (3.00, 15.00) → 3 + 15 = 18 USD
    assert compute_cost(1_000_000, 1_000_000, (3.00, 15.00)) == pytest.approx(18.0)


def test_compute_cost_scales_linearly():
    # 1000 in + 500 out at (3.0, 15.0) → 0.003 + 0.0075 = 0.0105
    assert compute_cost(1000, 500, (3.0, 15.0)) == pytest.approx(0.0105)


def test_pricing_tables_complete_for_documented_models():
    assert "claude-sonnet-4-6" in ANTHROPIC_PRICING
    assert "claude-opus-4-7" in ANTHROPIC_PRICING
    assert "gpt-4o" in OPENAI_PRICING
    assert "gemini-2.5-flash" in GEMINI_PRICING


# ─── provider factory ──────────────────────────────────────────

def test_make_provider_unknown_raises():
    with pytest.raises(ValueError, match="알 수 없는"):
        make_provider("nonexistent")


def test_make_provider_ollama_no_api_key_needed():
    p = make_provider("ollama")
    assert isinstance(p, OllamaProvider)
    assert p.name == "ollama"


def test_make_provider_anthropic_requires_api_key():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            make_provider("anthropic")


def test_make_provider_anthropic_with_explicit_key():
    p = make_provider("anthropic", api_key="sk-test")
    assert p.api_key == "sk-test"


def test_providers_registry_has_four():
    assert set(PROVIDERS.keys()) == {"ollama", "anthropic", "openai", "gemini"}


def test_available_providers_includes_ollama_always():
    """ollama는 키 없이도 후보. 클라우드는 키 있을 때만."""
    with patch.dict(os.environ, {}, clear=True):
        out = available_providers()
        assert "ollama" in out
        assert "anthropic" not in out
        assert "openai" not in out
        assert "gemini" not in out

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x", "GEMINI_API_KEY": "y"}, clear=True):
        out = available_providers()
        assert set(out) == {"ollama", "anthropic", "gemini"}


# ─── parse_yes_no ──────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("yes", True),
    ("Yes, 화면이 부합", True),
    ("YES", True),
    ("예", True),
    ("예, 맞습니다", True),
    ("맞습니다", True),
    ("no", False),
    ("No, 다릅니다", False),
    ("아니오", False),
    ("", False),
    ("   ", False),
    ("hmm 잘 모르겠지만 yes", False),  # 첫 단어만 본다
])
def test_parse_yes_no(text: str, expected: bool):
    assert parse_yes_no(text) is expected


# ─── run_bench (mock providers) ────────────────────────────────

@dataclass
class _MockProvider:
    name: str
    model: str
    responses: list[VisionResponse]
    _idx: int = 0

    def describe(self, image_bytes, prompt):
        r = self.responses[self._idx % len(self.responses)]
        self._idx += 1
        return r


def _mock_response(text: str, *, model="m1", provider="mock",
                    latency=100.0, tokens_in=10, tokens_out=5,
                    cost=0.001, error=None) -> VisionResponse:
    return VisionResponse(description=text, latency_ms=latency,
                            tokens_in=tokens_in, tokens_out=tokens_out,
                            cost_usd=cost, model=model, provider=provider,
                            error=error)


def _bench_item(scenario: str, gt_yes: bool, tmp_path: Path) -> BenchItem:
    img = tmp_path / f"{scenario}.png"
    img.write_bytes(b"fake png")
    return BenchItem(scenario=scenario, image_path=img,
                      expected="EPG 표시됨", ground_truth_yes=gt_yes)


def test_run_bench_correct_when_prediction_matches_truth(tmp_path: Path):
    items = [_bench_item("a", gt_yes=True, tmp_path=tmp_path)]
    provider = _MockProvider(name="mock", model="m1",
                              responses=[_mock_response("yes")])
    results = run_bench(items, [provider])
    assert len(results) == 1
    assert results[0].predicted_yes is True
    assert results[0].correct is True


def test_run_bench_incorrect_when_prediction_misses(tmp_path: Path):
    items = [_bench_item("a", gt_yes=True, tmp_path=tmp_path)]
    provider = _MockProvider(name="mock", model="m1",
                              responses=[_mock_response("no")])
    results = run_bench(items, [provider])
    assert results[0].correct is False


def test_run_bench_error_response_marks_incorrect(tmp_path: Path):
    items = [_bench_item("a", gt_yes=True, tmp_path=tmp_path)]
    provider = _MockProvider(name="mock", model="m1",
                              responses=[_mock_response("", error="rate limited")])
    results = run_bench(items, [provider])
    assert results[0].correct is False
    assert results[0].response.error == "rate limited"


def test_run_bench_runs_all_combinations(tmp_path: Path):
    items = [
        _bench_item("a", gt_yes=True, tmp_path=tmp_path),
        _bench_item("b", gt_yes=False, tmp_path=tmp_path),
    ]
    p1 = _MockProvider(name="p1", model="m1",
                        responses=[_mock_response("yes"), _mock_response("no")])
    p2 = _MockProvider(name="p2", model="m2",
                        responses=[_mock_response("yes"), _mock_response("yes")])
    results = run_bench(items, [p1, p2])
    assert len(results) == 4  # 2 items × 2 providers


# ─── summarize ─────────────────────────────────────────────────

def test_summarize_accuracy_and_error_rate():
    rs = [
        ProviderResult("p", "m1", "a", _mock_response("yes"), True, True),
        ProviderResult("p", "m1", "b", _mock_response("no"), False, False),
        ProviderResult("p", "m1", "c", _mock_response("yes"), True, True),
        ProviderResult("p", "m1", "d", _mock_response("", error="fail"), False, False),
    ]
    out = summarize(rs)
    assert out["p/m1"]["accuracy"] == pytest.approx(0.5)
    assert out["p/m1"]["error_rate"] == pytest.approx(0.25)
    assert out["p/m1"]["n"] == 4


def test_summarize_separates_by_provider_and_model():
    rs = [
        ProviderResult("p1", "m1", "a", _mock_response("yes"), True, True),
        ProviderResult("p2", "m2", "a", _mock_response("yes"), True, True),
    ]
    out = summarize(rs)
    assert set(out.keys()) == {"p1/m1", "p2/m2"}


def test_summarize_aggregates_cost_and_latency():
    rs = [
        ProviderResult("p", "m", "a", _mock_response("y", latency=100.0, cost=0.01), True, True),
        ProviderResult("p", "m", "b", _mock_response("y", latency=200.0, cost=0.02), True, True),
        ProviderResult("p", "m", "c", _mock_response("y", latency=300.0, cost=0.03), True, True),
    ]
    out = summarize(rs)["p/m"]
    assert out["total_cost_usd"] == pytest.approx(0.06)
    assert out["cost_per_call_usd"] == pytest.approx(0.02)
    assert out["latency_p50_ms"] == 200.0


# ─── rank_summary ──────────────────────────────────────────────

def _summary_row(acc=1.0, err=0.0, cost=0.001, latency=100.0):
    return {
        "accuracy": acc, "error_rate": err,
        "cost_per_call_usd": cost, "latency_p50_ms": latency,
        "latency_p95_ms": latency * 1.5, "total_cost_usd": cost * 10,
        "n": 10, "tokens_in_total": 100, "tokens_out_total": 50, "errors": 0,
    }


def test_rank_accuracy_first():
    summary = {
        "low/lm":  _summary_row(acc=0.70, cost=0.0001),
        "high/hm": _summary_row(acc=0.95, cost=0.01),
        "mid/mm":  _summary_row(acc=0.85, cost=0.001),
    }
    ranked = rank_summary(summary, "accuracy-first")
    assert [k for k, _ in ranked] == ["high/hm", "mid/mm", "low/lm"]


def test_rank_cost_first():
    summary = {
        "low/lm":  _summary_row(acc=0.70, cost=0.0001),
        "high/hm": _summary_row(acc=0.95, cost=0.01),
    }
    ranked = rank_summary(summary, "cost-first")
    assert [k for k, _ in ranked] == ["low/lm", "high/hm"]


def test_rank_latency_first():
    summary = {
        "fast/f": _summary_row(latency=50.0),
        "slow/s": _summary_row(latency=500.0),
    }
    ranked = rank_summary(summary, "latency-first")
    assert [k for k, _ in ranked] == ["fast/f", "slow/s"]


def test_rank_unknown_objective_raises():
    with pytest.raises(ValueError):
        rank_summary({}, "bogus")
