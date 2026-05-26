"""Vision provider 추상화 — Tier 3 yes/no 질의용 통합 인터페이스.

4종 구현:
  - OllamaProvider    : 로컬 (LLaVA / Qwen-VL)              — 비용 0, latency 큼
  - AnthropicProvider : Claude Sonnet 4.6 / Opus 4.7 / Haiku — 멀티모달 강점
  - OpenAIProvider    : GPT-4o / GPT-4o-mini                 — 비용/품질 균형
  - GeminiProvider    : gemini-2.5-flash / pro               — 비용 최저

각 provider는 동일 인터페이스로 (description, latency, tokens, cost) 반환.
SDK는 lazy import — 해당 provider를 실제로 호출할 때만 로드.
"""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field


@dataclass
class VisionResponse:
    description: str
    latency_ms: float
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    model: str = ""
    provider: str = ""
    error: str | None = None  # 실패 시 채워짐, description 비어있음


# ──────────────────────────────────────────────────────────────
# 가격표 (per 1M tokens, USD) — 2026-05 기준 공식가
# ──────────────────────────────────────────────────────────────

ANTHROPIC_PRICING = {
    "claude-opus-4-7":       (15.00, 75.00),
    "claude-sonnet-4-6":     ( 3.00, 15.00),
    "claude-haiku-4-5-20251001": (1.00,  5.00),
}

OPENAI_PRICING = {
    "gpt-4o":                ( 2.50, 10.00),
    "gpt-4o-mini":           ( 0.15,  0.60),
}

GEMINI_PRICING = {
    "gemini-2.5-flash":      ( 0.075, 0.30),
    "gemini-2.5-pro":        ( 1.25,  5.00),
    "gemini-2.0-flash":      ( 0.075, 0.30),
}


def compute_cost(tokens_in: int, tokens_out: int,
                  pricing_per_mtok: tuple[float, float]) -> float:
    """1M-token 단가표 기반 비용 (USD)."""
    in_p, out_p = pricing_per_mtok
    return (tokens_in * in_p + tokens_out * out_p) / 1_000_000


# ──────────────────────────────────────────────────────────────
# Providers
# ──────────────────────────────────────────────────────────────

class OllamaProvider:
    name = "ollama"

    def __init__(self, *, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or os.getenv("OLLAMA_URL",
                                                "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("VISION_MODEL", "llava:latest")

    def describe(self, image_bytes: bytes, prompt: str) -> VisionResponse:
        import httpx
        b64 = base64.b64encode(image_bytes).decode()
        t0 = time.perf_counter()
        try:
            r = httpx.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt,
                       "images": [b64], "stream": False},
                timeout=180,
            )
            r.raise_for_status()
        except Exception as e:
            return VisionResponse(description="", latency_ms=(time.perf_counter() - t0) * 1000,
                                    model=self.model, provider=self.name, error=str(e))
        body = r.json()
        return VisionResponse(
            description=body.get("response", ""),
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens_in=body.get("prompt_eval_count", 0),
            tokens_out=body.get("eval_count", 0),
            cost_usd=0.0,
            model=self.model,
            provider=self.name,
        )


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("ANTHROPIC_VISION_MODEL", "claude-sonnet-4-6")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY 필요")

    def describe(self, image_bytes: bytes, prompt: str) -> VisionResponse:
        from anthropic import Anthropic
        client = Anthropic(api_key=self.api_key)
        b64 = base64.b64encode(image_bytes).decode()
        t0 = time.perf_counter()
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/png", "data": b64,
                        }},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
        except Exception as e:
            return VisionResponse(description="", latency_ms=(time.perf_counter() - t0) * 1000,
                                    model=self.model, provider=self.name, error=str(e))
        text = "".join(getattr(b, "text", "") for b in resp.content)
        cost = compute_cost(resp.usage.input_tokens, resp.usage.output_tokens,
                             ANTHROPIC_PRICING.get(self.model, (3.0, 15.0)))
        return VisionResponse(
            description=text,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens_in=resp.usage.input_tokens,
            tokens_out=resp.usage.output_tokens,
            cost_usd=cost,
            model=self.model,
            provider=self.name,
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self, *, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 필요")

    def describe(self, image_bytes: bytes, prompt: str) -> VisionResponse:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        b64 = base64.b64encode(image_bytes).decode()
        t0 = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
                max_tokens=512,
            )
        except Exception as e:
            return VisionResponse(description="", latency_ms=(time.perf_counter() - t0) * 1000,
                                    model=self.model, provider=self.name, error=str(e))
        text = resp.choices[0].message.content or ""
        cost = compute_cost(resp.usage.prompt_tokens, resp.usage.completion_tokens,
                             OPENAI_PRICING.get(self.model, (2.5, 10.0)))
        return VisionResponse(
            description=text,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens_in=resp.usage.prompt_tokens,
            tokens_out=resp.usage.completion_tokens,
            cost_usd=cost,
            model=self.model,
            provider=self.name,
        )


class GeminiProvider:
    name = "gemini"

    def __init__(self, *, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
        self.api_key = (api_key
                         or os.getenv("GEMINI_API_KEY")
                         or os.getenv("GOOGLE_API_KEY"))
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY 또는 GOOGLE_API_KEY 필요")

    def describe(self, image_bytes: bytes, prompt: str) -> VisionResponse:
        from google import genai
        client = genai.Client(api_key=self.api_key)
        t0 = time.perf_counter()
        try:
            resp = client.models.generate_content(
                model=self.model,
                contents=[{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {
                            "mime_type": "image/png",
                            "data": base64.b64encode(image_bytes).decode(),
                        }},
                    ],
                }],
            )
        except Exception as e:
            return VisionResponse(description="", latency_ms=(time.perf_counter() - t0) * 1000,
                                    model=self.model, provider=self.name, error=str(e))
        text = resp.text or ""
        usage = resp.usage_metadata
        in_tok = getattr(usage, "prompt_token_count", 0)
        out_tok = getattr(usage, "candidates_token_count", 0)
        cost = compute_cost(in_tok, out_tok,
                             GEMINI_PRICING.get(self.model, (0.075, 0.30)))
        return VisionResponse(
            description=text,
            latency_ms=(time.perf_counter() - t0) * 1000,
            tokens_in=in_tok,
            tokens_out=out_tok,
            cost_usd=cost,
            model=self.model,
            provider=self.name,
        )


# ──────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────

PROVIDERS: dict[str, type] = {
    "ollama":    OllamaProvider,
    "anthropic": AnthropicProvider,
    "openai":    OpenAIProvider,
    "gemini":    GeminiProvider,
}


def make_provider(name: str, **kwargs):
    if name not in PROVIDERS:
        raise ValueError(f"알 수 없는 provider: {name}. 사용 가능: {list(PROVIDERS)}")
    return PROVIDERS[name](**kwargs)


def available_providers() -> list[str]:
    """API 키/env 충족된 provider만 반환 — bench 자동 선택용."""
    out = ["ollama"]  # 로컬은 항상 시도
    if os.getenv("ANTHROPIC_API_KEY"):
        out.append("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        out.append("openai")
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        out.append("gemini")
    return out
