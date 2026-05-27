"""컴포넌트 라벨링 — 룰(결정론) 1차 + LLM 2차 (순수 함수 + 프롬프트 빌더).

LogSage 합의: LLM 단독 금지. 결정론 룰 우선, 저신뢰 시에만 LLM 보강.
"""
from __future__ import annotations

import json
import re

from .components import CATEGORY_HINT, COMPONENTS, RULE_KEYWORDS
from .signature import FailureSignature


def label_by_rules(sig: FailureSignature) -> tuple[str, float, list[str]]:
    """(component, confidence, matched_keywords).

    error_tokens + vision_desc에서 컴포넌트별 키워드 히트 카운트. 최다 컴포넌트 선택.
    히트 없으면 카테고리 힌트(저신뢰), 그래도 없으면 unknown.
    """
    haystack = " ".join(sig.error_tokens).lower() + " " + (sig.vision_desc or "").lower()
    scores: dict[str, list[str]] = {}
    for comp, keywords in RULE_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in haystack]
        if hits:
            scores[comp] = hits

    if scores:
        # 히트 수 최다, 동률이면 COMPONENTS 우선순위
        best = max(scores.items(), key=lambda kv: (len(kv[1]), -COMPONENTS.index(kv[0])))
        comp, hits = best
        # confidence: 히트 수 기반 포화 (1히트=0.55, 2=0.7, 3+=0.85)
        conf = min(0.55 + 0.15 * (len(hits) - 1), 0.85)
        return comp, round(conf, 2), hits

    # 폴백: 카테고리 힌트
    if sig.category and sig.category in CATEGORY_HINT:
        return CATEGORY_HINT[sig.category], 0.30, []

    return "unknown", 0.0, []


def needs_llm(confidence: float, threshold: float = 0.55) -> bool:
    """룰 confidence가 임계 미만이면 LLM 2차 라벨링 권장."""
    return confidence < threshold


def build_llm_prompt(sig: FailureSignature) -> str:
    """LLM에 보낼 RCA 프롬프트. 컴포넌트 라벨 + root cause + confidence를 JSON으로 요청."""
    comps = ", ".join(c for c in COMPONENTS if c != "unknown")
    tokens = "\n".join(f"  - {t}" for t in sig.error_tokens[:10]) or "  (없음)"
    return f"""STB QA 실패를 분석해 컴포넌트를 분류하세요.

시나리오: {sig.scenario_id}
카테고리: {sig.category or '미상'}
기대 결과: {sig.expected or '미상'}
판정 tier: {sig.tier or 'n/a'}
화면 묘사(vision): {sig.vision_desc[:300] or '(없음)'}
UART 오류 토큰:
{tokens}
IR 키 시퀀스: {', '.join(sig.ir_keys) or '(없음)'}

가능한 컴포넌트: {comps}, unknown

다음 JSON만 출력하세요 (다른 텍스트 금지):
{{"component": "<위 중 하나>", "root_cause": "<한 줄 추정 원인>", "confidence": <0.0~1.0>}}"""


_JSON_OBJ = re.compile(r"\{.*\}", re.S)


def parse_llm_response(text: str) -> tuple[str, str, float]:
    """LLM 응답에서 component/root_cause/confidence 파싱. 실패 시 unknown."""
    m = _JSON_OBJ.search(text or "")
    if not m:
        return "unknown", "", 0.0
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return "unknown", "", 0.0
    comp = str(data.get("component", "unknown")).strip().lower()
    if comp not in COMPONENTS:
        comp = "unknown"
    root = str(data.get("root_cause", "")).strip()
    try:
        conf = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return comp, root, max(0.0, min(conf, 1.0))


def label(
    sig: FailureSignature,
    *,
    llm_fn=None,
    llm_threshold: float = 0.55,
) -> dict:
    """최종 라벨. llm_fn(prompt)->str 주어지고 룰 confidence 낮으면 LLM 보강.

    반환: {component, confidence, source, root_cause, matched_keywords}
    """
    comp, conf, hits = label_by_rules(sig)
    result = {
        "component": comp,
        "confidence": conf,
        "source": "rule",
        "root_cause": "",
        "matched_keywords": hits,
    }
    if llm_fn and needs_llm(conf, llm_threshold):
        try:
            llm_comp, root, llm_conf = parse_llm_response(llm_fn(build_llm_prompt(sig)))
        except Exception as e:  # LLM 실패는 룰 결과로 폴백
            result["llm_error"] = str(e)
            return result
        # LLM이 더 확신하면 채택
        if llm_conf >= conf:
            result.update(component=llm_comp, confidence=round(llm_conf, 2),
                          source="llm", root_cause=root)
    return result
