"""scenario-drafter CLI.

사용 예:
  # API 모드 (ANTHROPIC_API_KEY 필요)
  python -m tools.scenario_drafter.draft \\
      --spec docs/specs/example-disney-plus.md \\
      --output drafts/disney-plus.json

  # Fallback 모드 (API 키 없을 때) — 프롬프트만 stdout으로 출력
  # → Claude.ai / Claude Code에 붙여넣고 응답을 별도 저장 후 --validate
  python -m tools.scenario_drafter.draft \\
      --spec docs/specs/example-disney-plus.md \\
      --prompt-only

  # 검증만 (LLM 응답을 별도로 저장한 경우)
  python -m tools.scenario_drafter.draft \\
      --validate drafts/disney-plus.json

설계:
- Opus 4.7 + adaptive thinking + effort=high
- 시스템 프롬프트(스키마+어휘+예시)는 프롬프트 캐시 대상
- 응답에서 JSON 배열 추출 → pydantic Scenario로 시나리오별 검증
- 메인 카탈로그 머지는 별도 단계 — 사용자가 검토 후 수동/자동
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# 패키지/스크립트 양쪽에서 동작
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.catalog.schema import Scenario
    from tools.scenario_drafter.prompt import build_system_blocks, build_user_prompt
else:
    from ..catalog.schema import Scenario
    from .prompt import build_system_blocks, build_user_prompt


MODEL = "claude-opus-4-7"
MAX_TOKENS = 16000  # 30+ 시나리오 여유, 비스트림 SDK 타임아웃 안전 범위


# ──────────────────────────────────────────────────────────────
# JSON 추출 — 모델이 fence를 붙여 출력해도 살려냄
# ──────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"```(?:json)?\s*(\[.*\])\s*```", re.DOTALL)


def extract_json_array(text: str) -> str:
    """응답 텍스트에서 첫 JSON 배열을 추출. fence 있으면 벗긴다."""
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return text
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1)
    # fence 없이 머리/꼬리에 잡음이 붙은 경우 — 첫 [ ~ 마지막 ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    raise ValueError("응답에서 JSON 배열을 찾지 못함")


# ──────────────────────────────────────────────────────────────
# 검증 — pydantic Scenario로 시나리오별 검증, 실패 리포트
# ──────────────────────────────────────────────────────────────

def validate_draft(draft_json: str) -> tuple[list[dict], list[str]]:
    """(검증 통과한 시나리오 dict 리스트, 에러 메시지 리스트) 반환."""
    try:
        data = json.loads(draft_json)
    except json.JSONDecodeError as e:
        return [], [f"JSON parse 실패: {e}"]

    if not isinstance(data, list):
        return [], [f"top-level은 배열이어야 함, got {type(data).__name__}"]

    ok: list[dict] = []
    errors: list[str] = []
    for i, item in enumerate(data):
        sid = item.get("id", f"<index {i}>") if isinstance(item, dict) else f"<index {i}>"
        try:
            Scenario.model_validate(item)
            ok.append(item)
        except Exception as e:
            errors.append(f"{sid}: {e}")
    return ok, errors


# ──────────────────────────────────────────────────────────────
# Claude API 호출
# ──────────────────────────────────────────────────────────────

def call_claude(spec_text: str) -> tuple[str, dict]:
    """(응답 텍스트, usage dict) 반환. API 키 없으면 RuntimeError."""
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "anthropic 패키지 미설치. `pip install anthropic` 후 다시 실행하세요."
        ) from e

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY 환경변수 없음. --prompt-only로 실행해 프롬프트만 받거나 "
            "키를 설정한 후 재실행하세요."
        )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=build_system_blocks(),
        messages=[{"role": "user", "content": build_user_prompt(spec_text)}],
    )

    # 응답에서 텍스트만 추출 (thinking 블록은 건너뜀)
    text_parts = [b.text for b in response.content if b.type == "text"]
    text = "\n".join(text_parts).strip()

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(
            response.usage, "cache_creation_input_tokens", 0
        ),
        "cache_read_input_tokens": getattr(
            response.usage, "cache_read_input_tokens", 0
        ),
    }
    return text, usage


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def cmd_draft(args) -> int:
    spec_text = Path(args.spec).read_text(encoding="utf-8")

    if args.prompt_only:
        # API 없이 프롬프트만 stdout — Claude.ai/Claude Code 붙여넣기용
        print("=" * 60)
        print("# SYSTEM PROMPT (Claude UI는 이 내용을 system instructions 로 설정)")
        print("=" * 60)
        for block in build_system_blocks():
            print(block["text"])
        print()
        print("=" * 60)
        print("# USER PROMPT")
        print("=" * 60)
        print(build_user_prompt(spec_text))
        print()
        print(
            "→ Claude 응답을 별도 파일(예: drafts/foo.json)로 저장 후, "
            "`python -m tools.scenario_drafter.draft --validate drafts/foo.json` 실행"
        )
        return 0

    # API 모드
    try:
        text, usage = call_claude(spec_text)
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    # JSON 추출
    try:
        draft_json = extract_json_array(text)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        print(f"\n원본 응답:\n{text}", file=sys.stderr)
        return 3

    # 검증
    ok, errors = validate_draft(draft_json)

    # 결과 저장 (검증 통과한 것만)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(ok, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 리포트
    print(f"✅ {len(ok)} scenarios 통과 → {out_path}")
    if errors:
        print(f"⚠️  {len(errors)} 시나리오 검증 실패 (저장에서 제외됨):", file=sys.stderr)
        for err in errors:
            print(f"   - {err}", file=sys.stderr)

    print(
        f"\n📊 usage: input={usage['input_tokens']} "
        f"output={usage['output_tokens']} "
        f"cache_create={usage['cache_creation_input_tokens']} "
        f"cache_read={usage['cache_read_input_tokens']}"
    )
    if usage["cache_read_input_tokens"] == 0 and usage["cache_creation_input_tokens"] > 0:
        print("ℹ️  첫 호출이라 캐시 미스. 동일 시스템 프롬프트로 5분 내 재호출 시 ~10× 저렴.")

    return 0 if not errors else 1


def cmd_validate(args) -> int:
    text = Path(args.validate).read_text(encoding="utf-8")
    # 사용자가 fence 채로 저장했을 수 있으므로 추출 한 번 더
    try:
        draft_json = extract_json_array(text)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 3

    ok, errors = validate_draft(draft_json)
    print(f"✅ {len(ok)}/{len(ok) + len(errors)} 시나리오 v2 schema 통과")
    if errors:
        print(f"⚠️  {len(errors)} 시나리오 검증 실패:", file=sys.stderr)
        for err in errors:
            print(f"   - {err}", file=sys.stderr)
    return 0 if not errors else 1


def main():
    p = argparse.ArgumentParser(
        prog="scenario-drafter",
        description="한국어 STB 기능명세서 → v2 카탈로그 JSON 시나리오 초안",
    )
    p.add_argument("--spec", type=Path, help="입력 명세서 파일 (.md / .txt)")
    p.add_argument("--output", type=Path, help="JSON 출력 경로 (검증 통과만 저장)")
    p.add_argument(
        "--prompt-only",
        action="store_true",
        help="API 호출 없이 system/user 프롬프트를 stdout으로 출력 (Claude UI 붙여넣기용)",
    )
    p.add_argument(
        "--validate",
        type=Path,
        help="이미 저장된 LLM 응답 JSON을 v2 schema로만 검증",
    )
    args = p.parse_args()

    if args.validate:
        sys.exit(cmd_validate(args))

    if not args.spec:
        p.error("--spec 또는 --validate 중 하나 필요")
    if not args.prompt_only and not args.output:
        p.error("API 모드에서는 --output 필요 (또는 --prompt-only 사용)")

    sys.exit(cmd_draft(args))


if __name__ == "__main__":
    main()
