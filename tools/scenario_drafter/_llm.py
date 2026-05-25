"""LLM 공통 헬퍼 — scenario_drafter / excel_importer / edge_case_generator가 공유.

- Anthropic SDK 호출 (Opus 4.7, adaptive thinking, effort=high)
- 시스템 프롬프트 프롬프트 캐싱 (top-level cache_control)
- 응답에서 JSON 배열 추출 (fence 자동 제거)
- pydantic Scenario 검증
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# 패키지 import 경로 호환
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.catalog.schema import Scenario
else:
    from ..catalog.schema import Scenario


MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 16000


# ──────────────────────────────────────────────────────────────
# JSON 추출
# ──────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"```(?:json)?\s*(\[.*\]|\{.*\})\s*```", re.DOTALL)


def extract_json(text: str) -> str:
    """응답에서 첫 JSON 배열/객체 추출. fence 자동 제거."""
    text = text.strip()
    if (text.startswith("[") and text.endswith("]")) or (
        text.startswith("{") and text.endswith("}")
    ):
        return text
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1)
    for opener, closer in [("[", "]"), ("{", "}")]:
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
    raise ValueError("응답에서 JSON 추출 실패")


# ──────────────────────────────────────────────────────────────
# Scenario 검증
# ──────────────────────────────────────────────────────────────

def validate_scenarios(items: list[dict]) -> tuple[list[dict], list[str]]:
    """v2 Scenario로 시나리오별 검증. (통과, 에러 메시지)."""
    ok: list[dict] = []
    errors: list[str] = []
    for i, item in enumerate(items):
        sid = item.get("id", f"<index {i}>") if isinstance(item, dict) else f"<index {i}>"
        try:
            Scenario.model_validate(item)
            ok.append(item)
        except Exception as e:
            errors.append(f"{sid}: {e}")
    return ok, errors


# ──────────────────────────────────────────────────────────────
# Claude 호출
# ──────────────────────────────────────────────────────────────

def call_claude(
    system_text: str,
    user_text: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> tuple[str, dict]:
    """프롬프트 캐싱 활성화된 Claude 호출. (응답 텍스트, usage)."""
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "anthropic 패키지 미설치. `pip install anthropic` 후 재실행하세요."
        ) from e
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY 미설정. --prompt-only로 프롬프트만 출력하거나 키를 설정하세요."
        )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=[
            {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": user_text}],
    )
    text = "\n".join(b.text for b in response.content if b.type == "text").strip()
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


def format_usage(usage: dict[str, int]) -> str:
    return (
        f"input={usage['input_tokens']} "
        f"output={usage['output_tokens']} "
        f"cache_create={usage['cache_creation_input_tokens']} "
        f"cache_read={usage['cache_read_input_tokens']}"
    )
