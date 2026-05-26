"""Detection MCP v2 — 3-tier judge 파이프라인.

판정 흐름 (Phase 2, docs/29-judge-pipeline-v2.md):

  ┌───────────────────────────────────────────────────────────┐
  │  Tier 1: 임베딩 거리 (Qdrant baseline)                    │
  │   distance ≥ HARD_NORMAL  → verdict=normal,  즉시 종료    │
  │   distance <  HARD_ANOMALY → verdict=anomaly, 즉시 종료    │
  │   else ↓ (회색 지대)                                       │
  ├───────────────────────────────────────────────────────────┤
  │  Tier 2: 룰 매칭 (description ↔ expected 키워드)          │
  │   expected 키워드가 description에 충분히 포함됨           │
  │     → verdict=normal,  tier=rule                          │
  │   else ↓                                                  │
  ├───────────────────────────────────────────────────────────┤
  │  Tier 3: vision 재질의 (회색 지대 최종 보루)              │
  │   "이 화면이 expected와 부합?" 질의                        │
  │   → yes/no                                                │
  └───────────────────────────────────────────────────────────┘

Vision 모델은 단독 오라클 X — 회색 지대만 호출. 산업 합의(Witbe Agentic SDK,
Netflix RMSE dual-mode, docs/23 §2)에 부합.

응답 스키마:
  verdict        : "normal" | "anomaly" | "no_baseline"
  tier           : "embedding" | "rule" | "vision" | "no_baseline"
  best_score     : float — Qdrant 유사도 (1차에서 측정한 값)
  confidence     : float — 최종 판정 신뢰도 0~1
  description    : str — vision describe 결과
  rule_match     : dict | None — tier=rule일 때 매칭 키워드 정보
  vision_verdict : dict | None — tier=vision일 때 재질의 결과
"""
from __future__ import annotations

import os
import re

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="stb-detection-mcp", version="2.0")

BASELINE_URL = os.getenv("BASELINE_URL", "http://baseline-mcp:8000")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://embedding-mcp:8000")

# 3-tier 임계 (환경변수로 튜닝 가능)
THRESHOLD_HARD_NORMAL = float(os.getenv("THRESHOLD_HARD_NORMAL", "0.96"))   # 이 이상이면 즉시 normal
THRESHOLD_HARD_ANOMALY = float(os.getenv("THRESHOLD_HARD_ANOMALY", "0.85"))  # 이 미만이면 즉시 anomaly
RULE_MIN_KEYWORD_HITS = int(os.getenv("RULE_MIN_KEYWORD_HITS", "1"))         # 룰 통과 최소 키워드 수
VISION_TIER_ENABLED = os.getenv("VISION_TIER_ENABLED", "true").lower() == "true"


class ScreenCheckRequest(BaseModel):
    scenario: str
    image_base64: str
    firmware: str | None = None
    expected: str | None = None              # NEW v2: 룰 매칭용
    expected_keywords: list[str] | None = None   # NEW v2: 명시 키워드 (없으면 expected에서 자동 추출)


class LogCheckRequest(BaseModel):
    scenario: str
    log_text: str
    firmware: str | None = None


# ──────────────────────────────────────────────────────────────
# Tier 1: 임베딩 거리
# ──────────────────────────────────────────────────────────────

def _query_baseline(collection: str, vector: list[float], scenario: str) -> dict:
    r = httpx.post(
        f"{BASELINE_URL}/query",
        json={"collection": collection, "vector": vector, "scenario": scenario, "top_k": 1},
        timeout=10,
    )
    r.raise_for_status()
    hits = r.json().get("hits") or []
    return hits[0] if hits else {}


def _tier1_embedding(distance: float) -> tuple[str | None, float]:
    """(verdict, confidence) — None이면 회색 지대(다음 tier)."""
    if distance >= THRESHOLD_HARD_NORMAL:
        return "normal", distance
    if distance < THRESHOLD_HARD_ANOMALY:
        return "anomaly", 1.0 - distance
    return None, distance


# ──────────────────────────────────────────────────────────────
# Tier 2: 룰 매칭 (description ↔ expected 키워드)
# ──────────────────────────────────────────────────────────────

# 한국어/영어 명사·고유명사·숫자를 단순 추출
_KEYWORD_RE = re.compile(r"[A-Za-z0-9가-힣]+")
_STOPWORDS = {"의", "을", "를", "이", "가", "은", "는", "와", "과", "에", "에서",
              "표시", "표시됨", "화면", "결과", "후", "전", "the", "a", "an"}


def _extract_keywords(text: str) -> list[str]:
    """expected에서 매칭에 쓸 명사 후보 추출 (간단 휴리스틱)."""
    tokens = _KEYWORD_RE.findall(text)
    return [t for t in tokens if len(t) > 1 and t.lower() not in _STOPWORDS]


def _tier2_rule(description: str, expected: str | None,
                 expected_keywords: list[str] | None) -> dict | None:
    """description이 expected 키워드를 N개 이상 포함하면 match.

    반환: 매칭 정보 dict (verdict=normal로 종료할 근거) 또는 None.
    """
    if not (expected or expected_keywords):
        return None
    keywords = expected_keywords or _extract_keywords(expected or "")
    if not keywords:
        return None

    desc_lower = description.lower()
    hits = [kw for kw in keywords if kw.lower() in desc_lower]
    if len(hits) >= RULE_MIN_KEYWORD_HITS:
        return {
            "matched_keywords": hits,
            "all_keywords": keywords,
            "hit_ratio": len(hits) / len(keywords),
        }
    return None


# ──────────────────────────────────────────────────────────────
# Tier 3: vision 재질의
# ──────────────────────────────────────────────────────────────

def _tier3_vision(image_base64: str, expected: str) -> dict:
    """vision 모델에 'expected와 부합?' 직접 질의.

    embedding-mcp의 /vision/describe를 prompt 인자로 호출.
    반환: {match: bool, raw: str}
    """
    prompt = (
        f"다음 화면이 이 기대 결과와 부합하는지 yes/no로 답하세요.\n"
        f"기대 결과: {expected}\n"
        f"답변 형식: 'yes' 또는 'no' 한 단어로 시작하고, 이어서 짧은 근거."
    )
    try:
        r = httpx.post(
            f"{EMBEDDING_URL}/vision/describe",
            json={"image_base64": image_base64, "prompt": prompt},
            timeout=180,
        )
        r.raise_for_status()
        raw = r.json().get("description", "")
    except Exception as e:
        return {"match": False, "raw": "", "error": str(e)}

    first_word = raw.strip().split()[:1]
    is_yes = bool(first_word) and first_word[0].lower().startswith(("y", "예", "맞"))
    return {"match": is_yes, "raw": raw}


# ──────────────────────────────────────────────────────────────
# 통합 흐름
# ──────────────────────────────────────────────────────────────

def _describe_and_embed(image_base64: str) -> tuple[str, list[float]]:
    """이미지 → vision describe → 텍스트 임베딩."""
    desc_r = httpx.post(
        f"{EMBEDDING_URL}/vision/describe",
        json={"image_base64": image_base64},
        timeout=180,
    )
    desc_r.raise_for_status()
    description = desc_r.json()["description"]

    emb_r = httpx.post(f"{EMBEDDING_URL}/text", json={"text": description}, timeout=30)
    emb_r.raise_for_status()
    return description, emb_r.json()["embedding"]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "detection-mcp",
        "version": "2.0",
        "tiers": ["embedding", "rule", "vision" if VISION_TIER_ENABLED else "rule-only"],
        "thresholds": {
            "hard_normal": THRESHOLD_HARD_NORMAL,
            "hard_anomaly": THRESHOLD_HARD_ANOMALY,
            "rule_min_hits": RULE_MIN_KEYWORD_HITS,
        },
    }


@app.post("/check/screen")
def check_screen(req: ScreenCheckRequest):
    # 공통: describe + embed
    description, vector = _describe_and_embed(req.image_base64)
    top = _query_baseline("screen", vector, req.scenario)

    if not top:
        return {
            "verdict": "no_baseline",
            "tier": "no_baseline",
            "best_score": 0.0,
            "confidence": 0.0,
            "description": description,
            "hint": "베이스라인 등록 필요 (Phase 2 seed)",
        }

    distance = float(top["score"])
    base_payload = top.get("payload", {})

    # Tier 1: 임베딩 거리
    verdict, confidence = _tier1_embedding(distance)
    if verdict is not None:
        return {
            "verdict": verdict,
            "tier": "embedding",
            "best_score": distance,
            "confidence": confidence,
            "description": description,
            "baseline_payload": base_payload,
            "rule_match": None,
            "vision_verdict": None,
        }

    # Tier 2: 룰 매칭 (회색 지대)
    rule_match = _tier2_rule(description, req.expected, req.expected_keywords)
    if rule_match:
        return {
            "verdict": "normal",
            "tier": "rule",
            "best_score": distance,
            "confidence": 0.5 + 0.5 * rule_match["hit_ratio"],
            "description": description,
            "baseline_payload": base_payload,
            "rule_match": rule_match,
            "vision_verdict": None,
        }

    # Tier 3: vision 재질의 (활성화 시)
    if VISION_TIER_ENABLED and req.expected:
        v = _tier3_vision(req.image_base64, req.expected)
        return {
            "verdict": "normal" if v["match"] else "anomaly",
            "tier": "vision",
            "best_score": distance,
            "confidence": 0.6 if v["match"] else 0.7,
            "description": description,
            "baseline_payload": base_payload,
            "rule_match": None,
            "vision_verdict": v,
        }

    # vision 비활성 + 룰 실패 → 보수적으로 anomaly
    return {
        "verdict": "anomaly",
        "tier": "rule-fallthrough",
        "best_score": distance,
        "confidence": 0.5,
        "description": description,
        "baseline_payload": base_payload,
        "rule_match": None,
        "vision_verdict": None,
    }


@app.post("/check/log")
def check_log(req: LogCheckRequest):
    """로그 판정은 v1 유지 (Phase 2 우선순위 낮음 — 향후 별도 PR)."""
    emb_r = httpx.post(f"{EMBEDDING_URL}/text", json={"text": req.log_text}, timeout=30)
    emb_r.raise_for_status()
    vector = emb_r.json()["embedding"]
    top = _query_baseline("log", vector, req.scenario)
    if not top:
        return {"verdict": "no_baseline", "tier": "no_baseline", "best_score": 0.0}
    distance = float(top["score"])
    return {
        "verdict": "anomaly" if distance < THRESHOLD_HARD_ANOMALY else "normal",
        "tier": "embedding",
        "best_score": distance,
        "baseline_payload": top.get("payload", {}),
    }


@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "check/screen", "description": "DUT 화면 3-tier 판정 (임베딩 → 룰 → vision)"},
            {"name": "check/log", "description": "DUT 로그 임베딩 판정"},
        ]
    }
