"""Vision provider 비교 벤치 CLI — 골든셋 기반 Tier 3 모델 선정.

사용:
  # 환경에 등록된 모든 provider 자동 벤치
  python -m tools.vision_bench.cli

  # 특정 provider만 (콤마 구분)
  python -m tools.vision_bench.cli --providers ollama,anthropic

  # objective + 결과 저장
  python -m tools.vision_bench.cli --objective cost-first \\
      --save-report reports/vision-bench-2026-05-26.json

  # 모델 명시
  python -m tools.vision_bench.cli \\
      --providers anthropic,openai \\
      --anthropic-model claude-haiku-4-5-20251001 \\
      --openai-model gpt-4o-mini

필수 환경변수:
  ANTHROPIC_API_KEY     (anthropic provider 사용 시)
  OPENAI_API_KEY        (openai provider 사용 시)
  GEMINI_API_KEY 또는 GOOGLE_API_KEY   (gemini provider 사용 시)

ollama provider는 OLLAMA_URL (기본 localhost:11434) 만 도달 가능하면 됨.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.golden_set.schema import golden_set_root, load_all  # noqa: E402
from tools.vision_bench.providers import (  # noqa: E402
    available_providers, make_provider,
)
from tools.vision_bench.runner import (  # noqa: E402
    BenchItem, DEFAULT_PROMPT_TEMPLATE, rank_summary, run_bench, summarize,
)

CATALOG_PATH = (REPO_ROOT / "infrastructure" / "notebook-gateway"
                / "data" / "scenarios-catalog.json")


def _build_bench_items() -> list[BenchItem]:
    """골든셋 + 카탈로그 expected를 결합해 BenchItem 리스트 구성."""
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8")) if CATALOG_PATH.exists() else []
    expected_by_id = {s["id"]: s.get("expected", "") for s in catalog}

    items: list[BenchItem] = []
    for g in load_all():
        items.append(BenchItem(
            scenario=g.scenario_id,
            image_path=golden_set_root() / g.image_path,
            expected=expected_by_id.get(g.scenario_id, ""),
            ground_truth_yes=(g.ground_truth_verdict == "normal"),
        ))
    return items


def _print_ranked(ranked: list[tuple[str, dict]]) -> None:
    print("\n📊 ranked providers:")
    hdr = f"  {'provider/model':<40} {'acc':>6} {'err':>5} {'p50_ms':>8} {'p95_ms':>8} {'$/call':>9} {'total$':>8}"
    print(hdr)
    print("  " + "─" * (len(hdr) - 2))
    for key, m in ranked:
        print(f"  {key:<40} {m['accuracy']:>6.3f} {m['error_rate']:>5.2f} "
              f"{m['latency_p50_ms']:>8.0f} {m['latency_p95_ms']:>8.0f} "
              f"{m['cost_per_call_usd']:>9.5f} {m['total_cost_usd']:>8.4f}")


def _print_recommendation(ranked: list[tuple[str, dict]]) -> None:
    if not ranked:
        return
    best_key, _ = ranked[0]
    provider, model = best_key.split("/", 1)
    print("\n💡 권장 — embedding-mcp 환경변수에 설정:")
    print(f"  export VISION_PROVIDER={provider}")
    if provider == "anthropic":
        print(f"  export ANTHROPIC_VISION_MODEL={model}")
    elif provider == "openai":
        print(f"  export OPENAI_VISION_MODEL={model}")
    elif provider == "gemini":
        print(f"  export GEMINI_VISION_MODEL={model}")
    elif provider == "ollama":
        print(f"  export VISION_MODEL={model}")


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="vision-bench")
    ap.add_argument("--providers", default=None,
                    help="콤마 구분 (예: ollama,anthropic). 생략 시 환경 가능한 모든 provider")
    ap.add_argument("--objective", choices=["accuracy-first", "cost-first", "latency-first"],
                    default="accuracy-first")
    ap.add_argument("--ollama-model", default=None)
    ap.add_argument("--anthropic-model", default=None)
    ap.add_argument("--openai-model", default=None)
    ap.add_argument("--gemini-model", default=None)
    ap.add_argument("--save-report", type=Path,
                    help="JSON 리포트 저장 (provider/model별 metric + 원본 결과)")
    args = ap.parse_args()

    # 1. 골든셋 로드
    items = _build_bench_items()
    if not items:
        print("❌ 골든셋이 비어있음. tools.golden_set.label_cli로 라벨 후 재시도",
              file=sys.stderr)
        return 2

    # 2. provider 셋업
    requested = (args.providers.split(",") if args.providers
                  else available_providers())
    requested = [p.strip() for p in requested if p.strip()]
    if not requested:
        print("❌ 사용 가능한 provider가 없음. API 키 환경변수 확인", file=sys.stderr)
        return 2

    model_overrides = {
        "ollama":    args.ollama_model,
        "anthropic": args.anthropic_model,
        "openai":    args.openai_model,
        "gemini":    args.gemini_model,
    }
    providers = []
    for name in requested:
        try:
            kwargs = {"model": model_overrides[name]} if model_overrides.get(name) else {}
            providers.append(make_provider(name, **kwargs))
            print(f"✓ {name} 준비 완료 ({providers[-1].model})")
        except Exception as e:
            print(f"⊘ {name} 스킵: {e}")

    if not providers:
        print("❌ 초기화 성공한 provider가 없음", file=sys.stderr)
        return 2

    # 3. 벤치 실행
    print(f"\n🏃 벤치 시작 — {len(items)} 골든셋 × {len(providers)} provider "
          f"= {len(items) * len(providers)} API 호출")
    results = run_bench(items, providers)
    summary = summarize(results)
    ranked = rank_summary(summary, args.objective)

    # 4. 출력
    _print_ranked(ranked)
    _print_recommendation(ranked)

    if args.save_report:
        args.save_report.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "objective": args.objective,
            "n_items": len(items),
            "summary": summary,
            "ranking": [key for key, _ in ranked],
            "per_result": [{
                "provider": r.provider, "model": r.model, "scenario": r.scenario,
                "predicted_yes": r.predicted_yes, "correct": r.correct,
                "latency_ms": r.response.latency_ms,
                "tokens_in": r.response.tokens_in,
                "tokens_out": r.response.tokens_out,
                "cost_usd": r.response.cost_usd,
                "error": r.response.error,
            } for r in results],
        }
        args.save_report.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n📝 리포트 저장: {args.save_report.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
